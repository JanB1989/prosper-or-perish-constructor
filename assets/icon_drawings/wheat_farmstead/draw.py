"""Wheat Farmstead: a half-timbered farmhouse, a granary raised on staddle stones, a manure heap, ripe wheat.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/wheat_farmstead/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/wheat_farmstead

Identity (tier 1 of the wheat chain): the weatherboarded granary on mushroom-shaped staddle stones
(seed kept dry and away from rats) beside a timber-framed farmhouse with a shingle roof, a dark
steaming-brown manure heap with a fork at the front left, seed sacks, and a band of golden ripe
wheat across the front.

Helpers shared by the four wheat tiers: ``ears``, ``wheat_stand``, ``wheat_top``, ``stook``,
``furrows``, ``sprouts``, ``stubble``, ``thatch``, ``daub``; local to this tier: ``weatherboard``,
``staddle``, ``manure``, ``sack``.
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
REFS = ("farming_village", "granary", "fiber_crops_farm", "free_village")

GOLD = ((204, 146, 50), (238, 192, 96), (100, 60, 20))  # ear: mid, lit, dark
GOLD_FIELD = ("#b07c2c", "#76501e")
TIMBER = (112, 80, 52)


# ---------------------------------------------------------------------------- shared helpers
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _ell(cx, cy, L, w, ang, n=10):
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = math.cos(t) * L / 2, math.sin(t) * w / 2
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def ears(ic: Icon, items, clip: Image.Image | None = None, awns: bool = False) -> None:
    """Wheat ears (x, y, length, width, degrees, tone) in one blended layer; -90 points up.

    Dark body offset down-right, mid body, lit sliver on the upper-left side, grain notches, awns."""

    def paint(dr):
        for x, y, L, w, ang, f in items:
            mid, lit, dk = (tuple(int(min(255, v * f)) for v in c) for c in GOLD)
            a = math.radians(ang)
            if awns and L > 14:
                tip = (x + math.cos(a) * L * 0.45, y + math.sin(a) * L * 0.45)
                for da in (-12, 0, 12):
                    b = math.radians(ang + da)
                    dr.line([tip, (tip[0] + math.cos(b) * L * 0.5, tip[1] + math.sin(b) * L * 0.5)],
                            fill=lit + (140,), width=max(1, int(w * 0.13)))
            dr.polygon(_ell(x + w * 0.12, y + w * 0.12, L, w, ang), fill=dk + (255,))
            dr.polygon(_ell(x, y, L * 0.92, w * 0.84, ang), fill=mid + (255,))
            dr.polygon(_ell(x - w * 0.16, y - w * 0.1, L * 0.78, w * 0.4, ang), fill=lit + (215,))
            if L > 14:
                nx, ny = -math.sin(a), math.cos(a)
                for k in (-0.26, -0.02, 0.22):
                    cx, cy = x + math.cos(a) * L * k, y + math.sin(a) * L * k
                    dr.line([(cx - nx * w * 0.42, cy - ny * w * 0.42), (cx + nx * w * 0.1, cy + ny * w * 0.1)],
                            fill=dk + (130,), width=max(1, int(w * 0.12)))

    ic.overlay(paint, clip)


def wheat_stand(ic: Icon, x0: float, x1: float, base: float, h: float, rows: int = 4, scale: float = 1.0,
                clip: Image.Image | None = None) -> Image.Image:
    """Standing ripe wheat seen from the side: dark straw mass, stalks, rows of ears (back rows higher)."""
    rnd = ic.random
    top = [(x, base - h * 0.7 + rnd.uniform(-h * 0.05, h * 0.05)) for x in np.linspace(x0 + 6, x1 - 6, 26)]
    pts = [(x0, base)] + top + [(x1, base)]
    m = ic.poly_mask(pts)
    if clip is not None:
        m = ic.intersect(m, clip)
    ic.fill(m, "#a47228", "#442c10", (base - h, base), noise=0.3, chroma=0.12)

    def stalks(dr):
        for _ in range(int((x1 - x0) / 3)):
            x = rnd.uniform(x0, x1)
            yt = base - h * rnd.uniform(0.5, 0.9)
            col = rnd.choice(((200, 160, 78, 150), (110, 78, 36, 170), (228, 198, 120, 110)))
            dr.line([(x, base), (x + rnd.uniform(-7, 7), yt)], fill=col, width=3)

    ic.overlay(stalks, m)
    items, stems = [], []
    for r in range(rows):
        t = r / max(rows - 1, 1)
        y = base - h * (0.93 - 0.42 * t)
        f = 0.80 + 0.26 * t
        x = x0 + rnd.uniform(0, 16) * scale
        while x < x1 - 8:
            L = rnd.uniform(40, 52) * scale * (0.82 + 0.18 * t)
            yy = y + rnd.uniform(-12, 12) * scale
            ang = -90 + rnd.uniform(-24, 24) + (18 if rnd.random() < 0.3 else 0)
            items.append((x, yy, L, L * 0.29, ang, f * rnd.uniform(0.9, 1.08)))
            stems.append(((x, yy + L * 0.4), (x + rnd.uniform(-5, 5), yy + h * 0.45)))
            x += rnd.uniform(11, 17) * scale
    ic.overlay(lambda dr: [dr.line(s, fill=(96, 68, 30, 170), width=3) for s in stems], clip)
    items.sort(key=lambda it: it[1])
    ears(ic, items, clip)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - h * 0.28, SIZE, SIZE))), (30, 18, 6), 0.35, blur=14)
    return m


def wheat_top(ic: Icon, mask: Image.Image, y0: float, y1: float, x0: float, x1: float, step: float = 14,
              s0: float = 0.4) -> None:
    """Ripe field from above: ochre ground dense with small ears, smaller and paler towards the back."""
    rnd = ic.random
    ic.fill(mask, GOLD_FIELD[0], GOLD_FIELD[1], (y0, y1), noise=0.28, chroma=0.12)
    items = []
    y = y0 + 3
    while y < y1:
        s = s0 + (1 - s0) * (y - y0) / max(y1 - y0, 1)
        x = x0 + rnd.uniform(0, step * s)
        while x < x1:
            L = rnd.uniform(20, 28) * s
            items.append((x + rnd.uniform(-3, 3), y + rnd.uniform(-2, 2), L, L * 0.36, -90 + rnd.uniform(-30, 30),
                          rnd.uniform(0.82, 1.04) * (0.94 + 0.08 * s)))
            x += rnd.uniform(0.7, 1.1) * step * s
        y += step * 0.55 * s
    ears(ic, items, mask, awns=False)


def furrows(ic: Icon, bl, br, fl, fr, n: int = 7) -> Image.Image:
    """Ploughed strip: brown earth with ridges running along the strip."""
    m = ic.poly_mask([bl, br, fr, fl])
    ic.fill(m, "#7c5c3a", "#4c3620", (bl[1], fl[1]), noise=0.3, chroma=0.1)

    def paint(dr):
        for k in range(1, n):
            f = k / n
            p0, p1 = lerp(bl, br, f), lerp(fl, fr, f)
            dr.line([p0, p1], fill=(44, 30, 16, 170), width=6)
            dr.line([(p0[0] - 5, p0[1]), (p1[0] - 9, p1[1])], fill=(164, 130, 90, 110), width=4)

    ic.overlay(paint, m)
    return m


def sprouts(ic: Icon, bl, br, fl, fr, color=("#7a9440", "#4a6426")) -> Image.Image:
    """Young green crop in rows along the strip."""
    rnd = ic.random
    m = ic.poly_mask([bl, br, fr, fl])
    ic.fill(m, "#6a5234", "#4a3822", (bl[1], fl[1]), noise=0.3)

    def paint(dr):
        for k in range(1, 6):
            f = k / 6
            p0, p1 = lerp(bl, br, f), lerp(fl, fr, f)
            for t in np.linspace(0, 1, 40):
                x, y = lerp(p0, p1, t)
                s = 0.4 + 0.6 * t
                r = rnd.uniform(5, 9) * s
                c = rgb(color[0]) * rnd.uniform(0.8, 1.15)
                dr.ellipse((x - r * 1.3, y - r, x + r * 1.3, y + r * 0.6), fill=tuple(int(min(255, v)) for v in c) + (230,))

    ic.overlay(paint, m)
    return m


def stubble(ic: Icon, bl, br, fl, fr) -> Image.Image:
    """Reaped strip: pale straw stubble in short upright dashes."""
    rnd = ic.random
    m = ic.poly_mask([bl, br, fr, fl])
    ic.fill(m, "#c4aa6c", "#8c7040", (bl[1], fl[1]), noise=0.3, chroma=0.1)

    def paint(dr):
        y = bl[1] + 4
        while y < fl[1]:
            t = (y - bl[1]) / (fl[1] - bl[1])
            s = 0.4 + 0.6 * t
            xa, xb = lerp(bl, fl, t)[0], lerp(br, fr, t)[0]
            x = xa + rnd.uniform(0, 10)
            while x < xb:
                dr.line([(x, y), (x + rnd.uniform(-2, 2), y - 12 * s)], fill=(96, 72, 36, 170), width=3)
                dr.line([(x - 2, y - 1), (x - 2, y - 10 * s)], fill=(236, 216, 160, 120), width=2)
                x += rnd.uniform(9, 15) * s
            y += 10 * s

    ic.overlay(paint, m)
    return m


def stook(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Stook: sheaves of reaped wheat leaning together, tied at the waist, ears fanning at the top."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.62, base - 14, cx + w * 0.75, base + 16)), alpha=0.45, blur=8, clip=False)
    waist = base - h * 0.6
    body = [(cx - w * 0.5, base), (cx - w * 0.36, base - h * 0.3), (cx - w * 0.2, waist), (cx - w * 0.28, base - h * 0.8),
            (cx + w * 0.28, base - h * 0.82), (cx + w * 0.2, waist), (cx + w * 0.38, base - h * 0.3), (cx + w * 0.52, base)]
    m = ic.poly_mask(body)
    ic.fill(m, "#d6a850", "#664216", (cx - w * 0.4, cx + w * 0.5), vertical=False, noise=0.3, chroma=0.12)

    def straw(dr):
        for _ in range(int(w * 0.6)):
            xb = rnd.uniform(cx - w * 0.5, cx + w * 0.5)
            col = (238, 214, 150, 120) if rnd.random() < 0.5 else (90, 62, 26, 140)
            dr.line([(xb, base), (cx + (xb - cx) * 0.36, waist)], fill=col, width=3)
            xt = rnd.uniform(cx - w * 0.26, cx + w * 0.26)
            dr.line([(cx + (xt - cx) * 0.7, waist), (xt, base - h * 0.8)], fill=col, width=3)

    ic.overlay(straw, m)
    for f in (-0.18, 0.14):  # gaps between the sheaves
        ic.line([(cx + w * f * 0.4, waist + 6), (cx + w * f * 1.9, base - 2)], 5, (60, 40, 16, 150))
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx, 0, SIZE, SIZE))), (40, 24, 6), 0.25, blur=10)
    ic.line([(cx - w * 0.22, waist), (cx + w * 0.22, waist + 3)], 10, (120, 84, 38))
    ic.line([(cx - w * 0.2, waist - 3), (cx + w * 0.18, waist)], 3, (200, 164, 96, 180))
    items = []
    for _ in range(int(w / 9)):
        ang = -90 + rnd.uniform(-62, 62)
        a = math.radians(ang)
        d = rnd.uniform(0.1, 0.25) * h
        L = rnd.uniform(34, 44) * (h / 220)
        items.append((cx + math.cos(a) * d, base - h * 0.8 + math.sin(a) * d * 0.7, L, L * 0.32, ang,
                      rnd.uniform(0.9, 1.08)))
    items.sort(key=lambda it: it[1])
    ears(ic, items)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - 18, SIZE, SIZE))), (30, 20, 8), 0.4, blur=5)


def thatch(ic: Icon, ridge, eave, c=("#a88c58", "#5a4626")) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.22, 0.41, 0.6, 0.79, 1.0]
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
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 22, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 8, (150, 128, 84, 170))


def daub(ic: Icon, box, posts=()) -> None:
    """Wattle-and-daub wall: uneven ochre plaster, grime low down, rough posts."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, "#b89c6c", "#86704a", noise=0.3, edge=0)
    for _ in range(18):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(10, 26)
        light = rnd.random() < 0.5
        ic.shade(ic.mask("ellipse", (x - r * 1.5, y - r, x + r * 1.5, y + r)), (255, 240, 210) if light else (60, 40, 20),
                 0.14, blur=6)
    ic.shade(ic.mask("rectangle", (x0, y1 - 50, x1, y1)), (50, 44, 20), 0.35, blur=14)
    for x in posts:
        ic.rect((x - 11, y0, x + 11, y1), "#8e6644", "#4e3420", vertical=False, noise=0.25, edge=3)


def weather(ic: Icon, m: Image.Image, tone, n: int = 26) -> None:
    """Soften a roof: veil the course lines with the roof tone, add lichen and soot blotches."""
    rnd = ic.random
    ic.shade(m, tone, 0.3)
    box = m.getbbox()
    for _ in range(n):
        x, y = rnd.uniform(box[0], box[2]), rnd.uniform(box[1], box[3])
        r = rnd.uniform(14, 40)
        col = rnd.choice(((150, 150, 96), (40, 26, 16), (190, 150, 110)))
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - r * 1.6, y - r * 0.6, x + r * 1.6, y + r * 0.6))), col, 0.22,
                 blur=6)


def weatherboard(ic: Icon, box, c=("#9a6e46", "#5a3c22"), course: float = 30) -> None:
    """Horizontal clapboards: each board lit on top, shadowed under its lap, grain streaks."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, c[0], c[1], noise=0.25, edge=0)
    m = ic.mask("rectangle", box)
    y = y0
    while y < y1:
        t = rnd.uniform(0.9, 1.08)
        b = ic.mask("rectangle", (x0, y, x1, min(y + course, y1)))
        ic.shade(b, (255, 240, 210) if t > 1 else (0, 0, 0), abs(1 - t) * 1.4)
        ic.shade(ic.mask("rectangle", (x0, y + course - 8, x1, y + course)), (20, 12, 4), 0.45, blur=2)
        ic.shade(ic.mask("rectangle", (x0, y, x1, y + 5)), (255, 236, 200), 0.2)
        y += course

    def grain(dr):
        for _ in range(int((x1 - x0) * (y1 - y0) / 1800)):
            x, yy = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            dr.line([(x, yy), (x + rnd.uniform(30, 80), yy + rnd.uniform(-1, 1))], fill=(50, 30, 14, 60), width=2)

    ic.overlay(grain, m)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def staddle(ic: Icon, cx: float, top: float, base: float, w: float = 58) -> None:
    """Staddle stone: short tapering mid-grey stem under a mushroom cap that carries the granary sill."""
    ic.shade(ic.mask("ellipse", (cx - w * 0.7, base - 8, cx + w * 0.9, base + 10)), alpha=0.5, blur=5, clip=False)
    stem = [(cx - w * 0.44, base), (cx - w * 0.26, top + 16), (cx + w * 0.26, top + 16), (cx + w * 0.44, base)]
    ic.poly(stem, "#8c867a", "#4a463e", span=(cx - w * 0.44, cx + w * 0.44), vertical=False, noise=0.3, edge=3)
    ic.shade(ic.poly_mask(stem), (60, 64, 40), 0.2, blur=4)
    cap = (cx - w * 0.72, top - 4, cx + w * 0.72, top + 20)
    ic.fill(ic.mask("ellipse", cap), "#9a9486", "#58534a", radial=(cx - w * 0.5, top - 4, w * 1.6), noise=0.25)
    ic.overlay(lambda d: d.ellipse(cap, outline=(40, 34, 28, 200), width=4))
    ic.shade(ic.mask("ellipse", (cx - w * 0.55, top + 8, cx + w * 0.72, top + 22)), (0, 0, 0), 0.35, blur=3)


def manure(ic: Icon, x0: float, x1: float, base: float, top: float) -> Image.Image:
    """Manure heap: dark wet mound, lumps, flecks of old straw, a lighter dry crust on top."""
    rnd = ic.random
    cx = (x0 + x1) / 2
    pts = [(x0, base)]
    for t in np.linspace(0.05, 0.95, 16):
        x = x0 + (x1 - x0) * t
        y = base - (base - top) * math.sin(math.pi * t) ** 0.8 * rnd.uniform(0.92, 1.05)
        pts.append((x, y))
    pts.append((x1, base))
    m = ic.poly_mask(pts)
    ic.fill(m, "#a47c46", "#50361a", radial=(x0 + (x1 - x0) * 0.3, top, (x1 - x0) * 0.9), noise=0.4, chroma=0.12)
    for _ in range(22):
        x = rnd.uniform(x0 + 30, x1 - 30)
        yt = base - (base - top) * math.sin(math.pi * (x - x0) / (x1 - x0)) ** 0.8
        y = rnd.uniform(yt + 20, base - 10)
        r = rnd.uniform(14, 26)
        light = rnd.random() < 0.5
        ic.shade(ic.poly_mask(ic.jitter(x, y, r * 1.3, r, 7, 0.2)), (220, 190, 140) if light else (10, 6, 2),
                 0.16 if light else 0.3, blur=2)

    def straw(dr):
        for _ in range(int((x1 - x0) * 0.8)):
            x = rnd.uniform(x0 + 10, x1 - 10)
            yt = base - (base - top) * math.sin(math.pi * (x - x0) / (x1 - x0)) ** 0.8
            y = rnd.uniform(yt + 4, base - 4)
            a = rnd.uniform(0, math.pi)
            L = rnd.uniform(10, 24)
            col = (212, 176, 100, 170) if rnd.random() < 0.6 else (150, 112, 60, 170)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx + (x1 - x0) * 0.1, 0, SIZE, SIZE))), (30, 16, 4), 0.25, blur=20)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - 24, SIZE, SIZE))), (20, 10, 2), 0.3, blur=8)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (x0 + (x1 - x0) * 0.12, top - 20, x0 + (x1 - x0) * 0.7,
                                                  top + (base - top) * 0.45))), (255, 226, 160), 0.28, blur=10)
    return m


def sack(ic: Icon, cx: float, base: float, w: float, h: float, color) -> None:
    """Filled seed sack: lumpy body shaded from the upper left, tied neck."""
    body = ic.jitter(cx, base - h * 0.42, w * 0.5, h * 0.44, 14, 0.06)
    dark = tuple(int(v * 0.45) for v in rgb(color))
    ic.shade(ic.mask("ellipse", (cx - w * 0.6, base - 12, cx + w * 0.7, base + 12)), alpha=0.4, blur=6, clip=False)
    ic.fill(ic.poly_mask(body), color, dark, radial=(cx - w * 0.35, base - h * 0.8, w * 1.2), noise=0.3)
    ic.outline(body, 3, (40, 28, 16, 150))
    ic.poly([(cx - 10, base - h * 0.84), (cx - 16, base - h), (cx + 14, base - h * 1.02), (cx + 9, base - h * 0.84)],
            color, dark, edge=3)
    ic.line([(cx - 13, base - h * 0.86), (cx + 12, base - h * 0.86)], 5, (60, 44, 26))


# ---------------------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.84

    # ---- yard behind the field
    yard = [(30, 700), (60, 590), (990, 590), (1010, 720), (1010, 820), (20, 820)]
    ic.poly(yard, "#86704a", "#5c4a30", noise=0.32, edge=0)
    for _ in range(16):  # worn patches and puddle-dark ruts in the beaten earth
        x, y = rnd.uniform(80, 990), rnd.uniform(640, 780)
        r = rnd.uniform(14, 30)
        light = rnd.random() < 0.55
        ic.shade(ic.intersect(ic.poly_mask(yard), ic.mask("ellipse", (x - r * 2.2, y - r * 0.5, x + r * 2.2, y + r * 0.5))),
                 (230, 206, 150) if light else (40, 28, 14), 0.16, blur=6)

    # ---- farmhouse, left: half-timbered on a stone footing, shingle roof, chimney
    ic.shade(ic.mask("ellipse", (70, 620, 520, 690)), alpha=0.45, blur=10)
    ic.rect((396, 170, 444, 290), "#9a8a78", "#5e5246", edge=4)  # chimney behind the ridge
    ic.rect((388, 160, 452, 180), "#80746a", "#5a5048", edge=4)
    ic.plaster_frame((70, 400, 480, 610), posts=(76, 200, 320, 474), rails=(500,),
                     braces=(((76, 500), (140, 406)), ((474, 500), (410, 406))), wall="#d2bf98", wall_dark="#a8916a")
    ic.stonewall((64, 606, 486, 656), course=26)
    ic.door(236, 520, 296, 610, arched=False, surround=None)
    ic.window(118, 430, 166, 474)
    ic.window(372, 430, 420, 474)
    ic.window(372, 530, 420, 572)
    ic.shade(ic.mask("rectangle", (70, 400, 480, 460)), alpha=0.5, blur=12)
    hroof = [(28, 414), (522, 414), (452, 226), (98, 226)]
    ic.tiles(hroof, "#9c6a4a", "#5a3a26", course=30, stagger=40)
    weather(ic, ic.poly_mask(hroof), (150, 104, 76))
    ic.rect((92, 214, 458, 234), "#7e5a40", "#523624")
    ic.shade(ic.poly_mask([(300, 210), (540, 210), (540, 430), (330, 430)]), alpha=0.2, blur=40)

    # ---- granary on staddle stones, right
    GL, GR, GT, GB = 574, 868, 392, 574
    SB = GB + 70  # ground line under the staddles
    # dark gap under the granary floor: the building stands clear of the ground
    ic.rect((GL + 8, GB - 8, GR - 8, SB - 12), "#1c140c", "#3a2e1e", noise=0.2, edge=0)
    ic.shade(ic.mask("rectangle", (GL + 8, SB - 30, GR - 8, SB - 4)), (90, 74, 50), 0.5, blur=10)
    ic.shade(ic.mask("ellipse", (GL - 30, SB - 26, GR + 60, SB + 26)), alpha=0.4, blur=12, clip=False)
    for cx in (628, 812):  # back row, in the shadow
        staddle(ic, cx, GB - 4, SB - 14, 40)
    ic.shade(ic.mask("rectangle", (GL, GB, GR, SB - 10)), (10, 8, 4), 0.45, blur=4)
    for cx in (598, 722, 846):
        staddle(ic, cx, GB - 2, SB, 50)
    weatherboard(ic, (GL, GT, GR, GB))
    # open granary door: dark interior with a heap of grain and a sack
    ic.rect((664, 440, 772, 574), "#7a5230", "#442c18", edge=4)
    ic.rect((676, 452, 760, 574), "#2a1c10", "#140c06", noise=0.1, edge=0)
    gh = [(676, 574), (690, 532), (716, 506), (740, 520), (760, 548), (760, 574)]
    ic.poly(gh, "#e0b050", "#8a5a1c", edge=0, noise=0.3)
    ic.shade(ic.poly_mask(gh), (255, 236, 170), 0.3, blur=6)
    ic.shade(ic.mask("rectangle", (676, 452, 760, 500)), alpha=0.5, blur=8)
    ic.shade(ic.mask("rectangle", (GL, GT, GR, GT + 50)), alpha=0.5, blur=10)
    ic.shade(ic.mask("rectangle", (GL, GB - 30, GR, GB)), alpha=0.3, blur=8)
    groof = [(544, GT + 12), (898, GT + 12), (752, 214), (690, 214)]
    ic.tiles(groof, "#8a7458", "#4a3a2a", course=24, stagger=30)
    weather(ic, ic.poly_mask(groof), (130, 112, 90), 14)
    ic.shade(ic.poly_mask([(740, 230), (920, 230), (920, 410), (780, 410)]), alpha=0.22, blur=30)
    # sack pile in front of the granary door, two more sacks at the corner
    sack(ic, 668, 734, 62, 66, "#c29c66")
    sack(ic, 726, 744, 70, 76, "#d8b47c")
    sack(ic, 782, 738, 60, 62, "#cca676")
    sack(ic, 930, 736, 84, 104, "#d8b47c")
    sack(ic, 982, 750, 70, 84, "#c8a068")

    # ---- manure heap with a fork, back by the farmhouse corner
    hx0, hx1, hb, ht = 18, 238, 770, 636
    heap = manure(ic, hx0, hx1, hb, ht)
    fork = [(214, 660), (318, 548)]  # handle: a clear light diagonal
    ic.line(fork, 14, (46, 32, 18))
    ic.line([(fork[0][0] - 1, fork[0][1] - 1), (fork[1][0] - 1, fork[1][1] - 1)], 8, (214, 180, 128))
    ic.line([(fork[0][0] - 3, fork[0][1] - 2), (fork[1][0] - 3, fork[1][1] - 3)], 3, (248, 228, 186, 200))
    for dx in (-12, 0, 12):
        ic.line([(196 + dx, 690), (212 + dx * 0.6, 662)], 6, (70, 70, 72))
    ic.line([(194, 664), (228, 664)], 6, (70, 70, 72))

    # ---- ripe wheat along the front, from the far left
    fld = ic.poly_mask([(250, 748), (1010, 740), (1010, 860), (24, 860), (24, 800)])
    wheat_top(ic, fld, 740, 860, 24, 1010, step=18, s0=0.6)
    wheat_stand(ic, 24, 1010, 990, 250, rows=6, scale=1.15)
