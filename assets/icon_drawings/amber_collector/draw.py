"""Amber Gatherers (amber_collector): a reed-thatched shore hut on a Baltic beach, baskets of golden amber.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/amber_collector/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/amber_collector

Identity: two wicker baskets heaped with glowing golden amber on a pale sand beach at the edge of the
vanilla water band, a long-handled amber scoop net leaning on the big basket's rim, a heap of washed-up seaweed
with amber caught in it, and a low weathered-board hut with a tall grey reed roof behind.

Local helpers: ``amber`` (translucent lumps: dark rim, body, inner glow, glint), ``boards`` (weathered
vertical board wall), ``thatch`` (from coffee_grove, reed colours), ``seaweed`` (tangled wrack heap),
``rim_darken`` (from ocean_fishery).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 11
REFS = ("fishing_village", "salt_collector", "sand_pit", "pomor_outpost")

GOLD = ((255, 204, 84), (222, 124, 18), (112, 40, 4))
ORANGE = ((252, 170, 56), (200, 84, 12), (96, 28, 4))
HONEY = ((255, 222, 120), (232, 150, 36), (128, 60, 8))
COGNAC = ((240, 132, 44), (158, 50, 10), (72, 18, 4))
AMBERS = ((GOLD, 0.4), (ORANGE, 0.25), (HONEY, 0.2), (COGNAC, 0.15))

SAND = ("#e0c690", "#b08a52")
TIMBER = (112, 84, 58)


# ---------------------------------------------------------------- helpers
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


def amber(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Translucent amber lumps (x, y, r, palette) in one blended layer: dark rim, body, a glowing core
    offset away from the light (light passes through), a sharp glint at the upper left."""
    rnd = ic.random
    shapes = []
    for x, y, r, pal in items:
        base = ic.jitter(0, 0, r, r * rnd.uniform(0.7, 0.9), rnd.randint(10, 14), 0.1)
        shapes.append((x, y, r, pal, base))

    def paint(d):
        for x, y, r, (lit, mid, dk), base in shapes:
            def at(k, dx=0.0, dy=0.0, base=base, x=x, y=y):
                return [(x + dx + px * k, y + dy + py * k) for px, py in base]

            d.polygon(at(1.0), fill=dk + (255,))
            d.polygon(at(0.9, -r * 0.03, -r * 0.05), fill=mid + (255,))
            glow = tuple(int((a + b) / 2) for a, b in zip(mid, lit))
            d.polygon(at(0.68, r * 0.1, r * 0.08), fill=glow + (240,))
            d.polygon(at(0.4, r * 0.18, r * 0.14), fill=lit + (235,))
            g = max(r * 0.11, 2.5)
            gx, gy = x - r * 0.42, y - r * 0.32
            d.ellipse((gx - g * 1.5, gy - g * 0.8, gx + g * 1.5, gy + g * 0.8), fill=(255, 246, 214, 200))
            pts = at(1.0)
            d.line(pts + [pts[0]], fill=(80, 34, 6, 110), width=2)

    ic.overlay(paint, clip)


def amber_heap(ic: Icon, cx: float, top: float, base: float, hw: float, n: int, r: tuple[float, float]) -> None:
    """Dome of amber lumps between ``top`` and ``base``, back rows first."""
    rnd = ic.random
    # warm body under the lumps so no dark gaps show through the heap
    dome = [(cx + hw * u, base - (base - top) * 0.86 * math.sqrt(max(0.0, 1 - u * u)) ** 0.8)
            for u in np.linspace(-1, 1, 20)]
    dm = ic.poly_mask(dome)
    ic.fill(dm, "#d27a22", "#6a2808", radial=(cx - hw * 0.3, top, (base - top) * 1.6), noise=0.3)
    items = []
    for _ in range(n):
        u = rnd.uniform(-1, 1)
        h = math.sqrt(max(0.0, 1 - u * u))
        y = base - (base - top) * h * 0.92 * rnd.uniform(0.0, 1.0) ** 0.4
        items.append((cx + u * hw * 0.96, y, rnd.uniform(*r), pick(ic, AMBERS)))
    items.sort(key=lambda it: it[1])
    amber(ic, items)



def boards(ic: Icon, box, c=("#a88462", "#60462c"), w: float = 40) -> None:
    """Weathered vertical board wall: per-board tone, dark joints, faint grain, grime at the foot."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, c[0], c[1], edge=0, noise=0.22)
    x = x0
    while x < x1:
        bw = w * rnd.uniform(0.8, 1.25)
        b = (x, y0, min(x + bw, x1), y1)
        t = rnd.uniform(0.84, 1.1)
        ic.shade(ic.mask("rectangle", b), (0, 0, 0) if t < 1 else (255, 244, 220), abs(1 - t) * 1.7)

        def grain(d, b=b):
            for _ in range(3):
                gx = rnd.uniform(b[0] + 5, b[2] - 5)
                d.line([(gx, b[1] + rnd.uniform(0, 30)), (gx + rnd.uniform(-3, 3), b[3] - rnd.uniform(0, 40))],
                       fill=(40, 30, 20, 60), width=2)

        ic.overlay(grain)
        if b[2] < x1:
            ic.line([(b[2], y0), (b[2] + rnd.uniform(-2, 2), y1)], 4, (38, 28, 18, 190))
        x += bw
    ic.shade(ic.mask("rectangle", (x0, y1 - 60, x1, y1)), (30, 36, 20), 0.35, blur=16)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)


def thatch(ic: Icon, ridge, eave, c=("#bca46e", "#62502e")) -> None:
    """Reed roof plane seen from above: stalk strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.24, 0.45, 0.66, 0.84, 1.0]
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
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 24, 12), 0.45,
                     blur=6)
        tint = rnd.uniform(0.9, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])),
                (y0 - 10, y1 + 30), noise=0.32, chroma=0.12)

        def straw(dr, y0=y0, low=low):
            for _ in range(240):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (226, 214, 170, 80) if rnd.random() < 0.5 else (50, 42, 24, 85)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 24 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#7a6c48", "#443a22", (min(p[1] for p in eave), max(p[1] for p in eave) + 30),
            noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 22)], fill=(36, 28, 14, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 24, (92, 80, 54))
    ic.line([tuple(p) for p in ridge], 8, (150, 136, 100, 170))


def seaweed(ic: Icon, cx: float, base: float, hw: float, h: float) -> None:
    """Heap of washed-up wrack: dark olive mass, tangled strands, wet glints."""
    rnd = ic.random
    body = [(cx - hw, base)] + [(cx + hw * u, base - h * math.sqrt(max(0.0, 1 - u * u)) * rnd.uniform(0.75, 1.05))
                                for u in np.linspace(-0.9, 0.9, 12)] + [(cx + hw, base)]
    m = ic.poly_mask(body)
    ic.fill(m, "#6a6232", "#2c2812", radial=(cx - hw * 0.6, base - h, hw * 1.8), noise=0.35)

    def strands(d):
        for _ in range(26):
            x = rnd.uniform(cx - hw, cx + hw)
            y = rnd.uniform(base - h, base)
            pts = [(x, y)]
            for _ in range(5):
                x += rnd.uniform(10, 26) * rnd.choice((-1, 1))
                y += rnd.uniform(-10, 10)
                pts.append((x, y))
            col = (132, 120, 60, 170) if rnd.random() < 0.45 else (30, 26, 10, 170)
            d.line(pts, fill=col, width=rnd.randint(4, 8), joint="curve")

    ic.overlay(strands, m.filter(ImageFilter.MaxFilter(9)))
    ic.outline(body, 3, (30, 24, 10, 150))


def ramp(box, a0: float, a1: float, vertical: bool = False) -> Image.Image:
    """Mask that is ``box`` with a linear strength from ``a0`` to ``a1`` (0..1) across it."""
    x0, y0, x1, y1 = (int(v) for v in box)
    arr = np.zeros((SIZE, SIZE), float)
    if vertical:
        arr[y0:y1, x0:x1] = np.linspace(a0, a1, y1 - y0)[:, None]
    else:
        arr[y0:y1, x0:x1] = np.linspace(a0, a1, x1 - x0)[None, :]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype("uint8"))


def pebbles(ic: Icon, items) -> None:
    """Small beach stones (x, y, r): lit top, dark underside, a contact shadow."""
    for x, y, r in items:
        ic.shade(ic.mask("ellipse", (x - r * 1.2, y, x + r * 1.5, y + r * 0.9)), (40, 28, 14), 0.45, blur=3)
        tone = ic.random.uniform(0.8, 1.15)
        c1 = tuple(int(min(255, v * tone)) for v in (176, 168, 150))
        c2 = tuple(int(v * tone) for v in (84, 76, 66))
        pts = ic.jitter(x, y, r, r * 0.66, 10, 0.12)
        ic.fill(ic.poly_mask(pts), c1, c2, radial=(x - r * 0.5, y - r * 0.6, r * 1.8), noise=0.2)
        ic.outline(pts, 2, (50, 40, 30, 160))


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


# ---------------------------------------------------------------- scene
def beach(ic: Icon, band: Image.Image) -> list:
    rnd = ic.random
    back = [(x, 574 + rnd.uniform(-10, 8)) for x in np.linspace(34, 992, 14)]
    front = [(x, 734 + 16 * math.sin(x / 120) + rnd.uniform(-6, 6)) for x in np.linspace(1002, 22, 22)]
    pts = back + front
    m = ic.poly_mask(pts)
    ic.fill(m, SAND[0], SAND[1], (574, 760), noise=0.24, chroma=0.12)
    # wet sand along the waterline and wind ripples
    ic.shade(ic.intersect(m, ic.poly_mask(front + [(x, y - 46) for x, y in front[::-1]])), (70, 50, 26), 0.35, blur=14)

    def ripples(d):
        for _ in range(60):
            x, y = rnd.uniform(40, 990), rnd.uniform(590, 720)
            L = rnd.uniform(30, 70)
            d.arc((x, y - 6, x + L, y + 6), 200, 340, fill=(255, 246, 220, 70), width=3)
            d.arc((x + 4, y - 2, x + L + 4, y + 10), 200, 340, fill=(80, 60, 30, 60), width=3)
        for _ in range(50):  # pebbles and shell grit
            x, y = rnd.uniform(40, 990), rnd.uniform(590, 740)
            r = rnd.uniform(3, 7)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(96, 84, 70, 150) if rnd.random() < 0.6 else (236, 228, 210, 160))

    ic.overlay(ripples, m)
    # the left third lies in the hut's shade and is damper: darker sand
    ic.shade(ic.intersect(m, ic.mask("ellipse", (-160, 560, 560, 820))), (56, 38, 16), 0.42, blur=30)
    wet = [(x, y - 7) for x, y in front]
    ic.line(wet, 7, (70, 50, 28, 150))
    ic.line([(x, y - 14) for x, y in front], 3, (250, 238, 210, 90))
    ic.outline(pts, 4)
    # foam where the sea meets the sand
    def foam(d):
        for x, y in front:
            for k in range(2):
                L = rnd.uniform(24, 50)
                yy = y + 10 + k * 16 + rnd.uniform(-3, 4)
                d.line([(x - L / 2, yy), (x + L / 2, yy + rnd.uniform(-3, 3))], fill=(236, 246, 246, 220), width=7)

    ic.overlay(foam, band)
    return front


def hut(ic: Icon) -> None:
    rnd = ic.random
    X0, X1, Y0, Y1 = 84, 432, 404, 656
    # cast shadow on the sand to the lower right
    ic.shade(ic.poly_mask([(X1 - 10, 470), (X1 + 70, 540), (X1 + 90, Y1 + 18), (X1 - 10, Y1 + 18)]), (60, 40, 20), 0.35,
             blur=18)
    ic.shade(ic.mask("ellipse", (X0 - 40, Y1 - 20, X1 + 50, Y1 + 34)), (50, 34, 16), 0.45, blur=12)
    boards(ic, (X0, Y0, X1, Y1))
    # the front turns away from the light: lit on the left, darker to the right
    ic.shade(ramp((X0, Y0, X1, Y1), 0.28, 0.0), (255, 236, 200))
    ic.shade(ramp((X0, Y0, X1, Y1), 0.0, 0.62), (26, 18, 10))
    # low doorway (dark, a plank door standing ajar) and a small shuttered window
    ic.rect((190, 500, 284, Y1), "#2a2018", "#120c08", edge=4)
    door = [(190, 500), (224, 512), (224, Y1 + 6), (190, Y1)]
    ic.poly(door, "#7c5c3c", "#4a3422", edge=4)
    ic.line([(198, 540), (218, 546)], 6, (40, 38, 38))
    ic.line([(198, 614), (218, 618)], 6, (40, 38, 38))
    ic.rect((330, 496, 390, 546), "#2c2620", "#141010", edge=4)
    ic.rect((320, 486, 400, 498), "#8a6c4c", "#5a442c", edge=3)
    # corner posts and sill beam
    for x in (X0 + 8, X1 - 8):
        ic.rect((x - 12, Y0 - 6, x + 12, Y1), "#7a6044", "#46341f", vertical=False, edge=3)
    ic.rect((X0 - 6, Y1 - 16, X1 + 6, Y1 + 2), "#6a523a", "#3e2e1c", edge=3)
    # deep shadow band under the eave
    ic.shade(ic.intersect(ic.mask("rectangle", (X0 - 10, 440, X1 + 10, 508)), ramp((0, 440, SIZE, 520), 1, 0.2,
                                                                                      vertical=True)),
             (18, 12, 6), 0.7, blur=8)
    # tall reed roof
    ridge = [(158, 150), (258, 140), (358, 148)]
    eave = [(x, 432 + rnd.uniform(-5, 6)) for x in np.linspace(30, 486, 18)]
    thatch(ic, ridge, eave)
    ic.shade(ic.poly_mask([(300, 130), (500, 130), (500, 480), (330, 480)]), alpha=0.18, blur=40)
    ic.shade(ic.mask("rectangle", (X0, Y0, X1, Y0 + 70)), alpha=0.45, blur=12)
    # a pair of oars leaning on the left wall
    for (x0, y0), (x1, y1) in (((60, 660), (112, 300)), ((80, 664), (146, 320))):
        ic.line([(x0, y0), (x1, y1)], 14, (40, 28, 18, 220))
        ic.line([(x0, y0), (x1, y1)], 9, (156, 118, 78))
    for x, y in ((66, 646), (84, 650)):
        ic.poly([(x - 16, y - 90), (x + 12, y - 92), (x + 8, y + 8), (x - 12, y + 10)], "#a07650", "#5e4228", edge=3)


NET = dict(cx=578.0, cy=252.0, rx=66.0, ry=30.0, foot=(884.0, 752.0), top=(698.0, 236.0))


def net_bag(ic: Icon) -> None:
    """Back of the scoop net: the mesh bag hanging from the hoop (drawn behind the big basket)."""
    cx, cy, rx, ry = NET["cx"], NET["cy"], NET["rx"], NET["ry"]
    ts = np.linspace(0, 1, 16)
    bag_l = [(cx - rx + (rx * 0.8) * t + 8 * math.sin(math.pi * t) - 24 * t, cy + (172 * t)) for t in ts]
    bag_r = [(cx + rx - (rx * 0.85) * t + 9 * math.sin(math.pi * t) - 24 * t, cy + (150 * t)) for t in ts]
    bag = bag_l + [(cx - 30, cy + 184)] + bag_r[::-1]
    ic.net(bag, back="#a88a5a", back_dark="#5a4428", mesh=22)
    amber(ic, [(cx - 26, cy + 120, 14, GOLD), (cx - 6, cy + 132, 12, ORANGE)])
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 180, 360, fill=(40, 28, 18, 230), width=14))
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 180, 360, fill=(150, 112, 72, 255), width=8))


def net_pole(ic: Icon) -> None:
    """Front of the scoop net: the long handle leaning on the big basket's rim, and the hoop's front."""
    cx, cy, rx, ry = NET["cx"], NET["cy"], NET["rx"], NET["ry"]
    f, t = np.array(NET["foot"]), np.array(NET["top"])
    d = (t - f) / np.linalg.norm(t - f)
    n = np.array([-d[1], d[0]])  # points to the left of the handle (towards the light)
    ic.beam(tuple(f), tuple(t), 22, (140, 104, 66))
    ic.line([tuple(f + n * 7), tuple(t + n * 7)], 6, (204, 166, 116))
    ic.line([tuple(f - n * 7), tuple(t - n * 7)], 6, (78, 54, 32))
    # contact shadow where the handle rests on the rim
    ic.shade(ic.mask("ellipse", (770, 500, 830, 540)), (20, 12, 4), 0.5, blur=6)
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 0, 180, fill=(40, 28, 18, 240), width=16))
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 0, 180, fill=(164, 124, 80, 255), width=9))
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 20, 110, fill=(206, 170, 120, 200), width=3))
    # lashing where the hoop meets the handle
    ic.line([tuple(t - d * 10), (cx + rx - 6, cy + 4)], 16, (40, 28, 18))
    ic.line([tuple(t - d * 10), (cx + rx - 6, cy + 4)], 9, (150, 112, 72))
    ic.line([tuple(t + d * 4), tuple(t - d * 22)], 14, (70, 52, 32))


def sieve(ic: Icon, box) -> None:
    x0, y0, x1, y1 = box
    inner = (x0 + 16, y0 + 14, x1 - 16, y1 - 14)
    ic.fill(ic.mask("ellipse", box), "#8a6a44", "#4e3a22", (y0, y1), noise=0.2)
    ic.fill(ic.mask("ellipse", inner), "#4a3c2a", "#2a2016", (y0, y1), noise=0.15)
    m = ic.mask("ellipse", inner)

    def mesh(d):
        for x in np.arange(x0, x1, 12):
            d.line([(x, y0), (x, y1)], fill=(170, 150, 110, 150), width=2)
        for y in np.arange(y0, y1, 12):
            d.line([(x0, y), (x1, y)], fill=(170, 150, 110, 150), width=2)

    ic.overlay(mesh, m)
    ic.overlay(lambda d: d.arc(box, 150, 300, fill=(214, 180, 130, 180), width=5))
    ic.overlay(lambda d: d.ellipse(box, outline=(40, 28, 16, 220), width=4))


def basket_of_amber(ic: Icon, x0, y0, x1, y1, heap_top, n, r) -> None:
    w = x1 - x0
    ic.shade(ic.mask("ellipse", (x0 - 20, y1 - 22, x1 + 40, y1 + 22)), (50, 34, 16), 0.5, blur=10)
    ic.fill(ic.mask("ellipse", (x0 - 2, y0 - 22, x1 + 2, y0 + 22)), "#3a220c", "#1e1206")
    amber_heap(ic, (x0 + x1) / 2, heap_top, y0 + 14, w * 0.47, n, r)
    ic.basket(x0, y0, x1, y1, colors=("#94703e", "#4a3218"))
    ic.line([(x0 + 2, y0), (x1 - 2, y0)], 14, (104, 76, 44))
    ic.line([(x0 + 2, y0 - 4), (x1 - 2, y0 - 4)], 4, (190, 156, 104, 170))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.88
    band = ic.water_band(top=700, bottom=852, sag=34)
    ic.shade(ic.intersect(band, ic.mask("rectangle", (0, 820, SIZE, SIZE))), alpha=0.3, blur=14)
    beach(ic, band)
    hut(ic)
    pebbles(ic, [(40, 698, 17), (104, 716, 12), (184, 690, 15), (236, 718, 10), (306, 700, 13), (356, 724, 9),
                 (150, 728, 9), (404, 704, 10)])
    net_bag(ic)
    seaweed(ic, 458, 734, 96, 54)
    amber(ic, [(430, 700, 15, GOLD), (486, 694, 13, HONEY), (462, 716, 14, ORANGE), (520, 718, 12, GOLD)])
    basket_of_amber(ic, 520, 512, 800, 718, 340, 150, (22, 32))
    net_pole(ic)
    basket_of_amber(ic, 816, 610, 968, 738, 506, 70, (17, 25))
    amber(ic, [(620, 734, 14, GOLD), (700, 740, 12, COGNAC), (772, 728, 15, HONEY), (870, 752, 11, ORANGE),
               (668, 752, 10, GOLD)])
    rim_darken(ic)
