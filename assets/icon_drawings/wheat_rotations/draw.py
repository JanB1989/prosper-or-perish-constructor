"""Wheat Rotation Farm: a stone barn and a clover rick above hedged fields where wheat alternates with leys.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/wheat_rotations/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/wheat_rotations

Identity (tier 2 of the wheat chain): a checker of hedged fields, golden ripe wheat taking turns with
deep-green clover (pink and white heads) and a pea ley, standing wheat along the front; behind them a
tiled stone barn with a gabled wagon porch full of hay and a rick of clover hay under a thatched cap.

Helpers shared by the four wheat tiers: ``ears``, ``wheat_stand``, ``wheat_top``, ``stook``,
``furrows``, ``sprouts``, ``stubble``, ``thatch``, ``daub``; local to this tier: ``weatherboard``,
``clover``, ``peas``, ``hedge``, ``rick``.
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 47
REFS = ("farming_village", "fiber_crops_farm", "terraces", "sheep_farms")

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


def weather(ic: Icon, m: Image.Image, tone) -> None:
    """Soften a tiled roof: veil the course lines with the roof tone, add lichen and soot blotches."""
    rnd = ic.random
    ic.shade(m, tone, 0.3)
    box = m.getbbox()
    for _ in range(26):
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
        y += course

    def grain(dr):
        for _ in range(int((x1 - x0) * (y1 - y0) / 1800)):
            x, yy = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            dr.line([(x, yy), (x + rnd.uniform(30, 80), yy + rnd.uniform(-1, 1))], fill=(50, 30, 14, 60), width=2)

    ic.overlay(grain, m)


def clover(ic: Icon, pts, y0: float, y1: float, flowers=((214, 120, 150), (236, 226, 214))) -> Image.Image:
    """Clover ley from above: deep green, trefoil dabs, pink and white flower heads (smaller at the back)."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ic.fill(m, "#46702a", "#223a12", (y0, y1), noise=0.3, chroma=0.12)
    xs = [p[0] for p in pts]

    def paint(dr):
        y = y0 + 4
        while y < y1:
            s = 0.45 + 0.55 * (y - y0) / (y1 - y0)
            x = min(xs) + rnd.uniform(0, 10)
            while x < max(xs):
                r = rnd.uniform(6, 10) * s
                g = rnd.uniform(0.7, 1.15)
                col = (int(min(255, 92 * g)), int(min(255, 138 * g)), int(min(255, 52 * g)), 210)
                for a in (-90, 30, 150):
                    ax, ay = x + math.cos(math.radians(a)) * r, y + math.sin(math.radians(a)) * r * 0.6
                    dr.ellipse((ax - r, ay - r * 0.7, ax + r, ay + r * 0.7), fill=col)
                if rnd.random() < 0.12:
                    fc = rnd.choice(flowers)
                    fr = r * 1.1
                    dr.ellipse((x - fr + 2, y - fr * 1.6 + 2, x + fr + 2, y - fr * 0.1 + 2), fill=(40, 30, 30, 160))
                    dr.ellipse((x - fr, y - fr * 1.6, x + fr, y - fr * 0.1), fill=fc + (255,))
                    dr.ellipse((x - fr * 0.6, y - fr * 1.5, x, y - fr * 0.9), fill=(255, 240, 240, 150))
                x += rnd.uniform(12, 20) * s
            y += 11 * s

    ic.overlay(paint, m)
    return m


def peas(ic: Icon, pts, y0: float, y1: float) -> Image.Image:
    """Pulse ley from above: rows of blue-green pea haulm with a few white flowers."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ic.fill(m, "#5e5236", "#3e3422", (y0, y1), noise=0.3)
    xs = [p[0] for p in pts]

    def paint(dr):
        y = y0 + 6
        while y < y1:
            s = 0.45 + 0.55 * (y - y0) / (y1 - y0)
            x = min(xs)
            while x < max(xs):
                r = rnd.uniform(7, 11) * s
                g = rnd.uniform(0.85, 1.15)
                dr.ellipse((x - r * 1.4, y - r, x + r * 1.4, y + r * 0.5),
                           fill=(int(96 * g), int(140 * g), int(64 * g), 235))
                if rnd.random() < 0.12:
                    dr.ellipse((x - 4 * s, y - r - 4 * s, x + 4 * s, y - r + 4 * s), fill=(240, 236, 226, 255))
                x += rnd.uniform(9, 14) * s
            y += 22 * s

    ic.overlay(paint, m)
    return m


def hedge(ic: Icon, path, r0: float, r1: float) -> None:
    """Hedgerow along ``path`` (back to front): overlapping dark bushes, larger towards the viewer."""
    rnd = ic.random
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    total = seg.sum()
    ends = np.cumsum(seg)
    d = 0.0
    while d < total:
        i = min(int(np.searchsorted(ends, d)), len(seg) - 1)
        t = (d - (ends[i] - seg[i])) / seg[i]
        x, y = pts[i] + (pts[i + 1] - pts[i]) * t
        r = (r0 + (r1 - r0) * d / total) * rnd.uniform(0.8, 1.15)
        bm = ic.poly_mask(ic.jitter(x, y - r * 0.5, r * 1.15, r * 0.8, 12, 0.12))
        ic.fill(bm, "#557a30", "#1a2c0e", radial=(x - r * 0.7, y - r * 1.2, r * 2.2), noise=0.35, chroma=0.14)

        def dabs(dr, x=x, y=y, r=r):
            for _ in range(10):
                a = rnd.uniform(0, 2 * math.pi)
                rr = rnd.uniform(0, r * 0.9)
                px, py = x + math.cos(a) * rr, y - r * 0.5 + math.sin(a) * rr * 0.7
                k = rnd.uniform(2, 5)
                col = (150, 178, 92, 90) if py < y - r * 0.5 else (14, 24, 8, 90)
                dr.ellipse((px - k, py - k * 0.7, px + k, py + k * 0.7), fill=col)

        ic.overlay(dabs, bm)
        d += r * 0.9


def rick(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Rick of clover hay: rounded body of greenish hay under a small thatched cap, a ladder."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.6, base - 16, cx + w * 0.62, base + 16)), alpha=0.45, blur=8)
    body = [(cx - w * 0.44, base), (cx - w * 0.52, base - h * 0.22), (cx - w * 0.5, base - h * 0.42),
            (cx - w * 0.36, base - h * 0.58), (cx + w * 0.36, base - h * 0.58), (cx + w * 0.5, base - h * 0.42),
            (cx + w * 0.52, base - h * 0.22), (cx + w * 0.44, base)]
    m = ic.poly_mask(body)
    ic.fill(m, "#b4a660", "#564822", (cx - w * 0.5, cx + w * 0.5), vertical=False, noise=0.35, chroma=0.14)

    def hay(dr):
        for _ in range(500):
            x, y = rnd.uniform(cx - w * 0.55, cx + w * 0.55), rnd.uniform(base - h * 0.64, base)
            a = rnd.uniform(-0.6, 0.6)
            L = rnd.uniform(10, 22)
            col = (206, 196, 128, 110) if rnd.random() < 0.5 else (54, 58, 24, 110)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(hay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - 30, SIZE, SIZE))), alpha=0.35, blur=10)
    cap_r = [(cx - w * 0.14, base - h), (cx + w * 0.14, base - h)]
    cap_e = [(x, base - h * 0.56 + rnd.uniform(-4, 6)) for x in np.linspace(cx - w * 0.6, cx + w * 0.6, 12)]
    thatch(ic, cap_r, cap_e)
    ic.line([(cx, base - h - 10), (cx, base - h - 36)], 8, (90, 66, 40))


# ---------------------------------------------------------------------------- drawing
FB, FM, FF = 604, 744, 934  # field back, middle hedge, front edge


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.80

    # ---- enclosed fields: two rows of three, wheat alternating with clover and peas
    back = [70, 380, 680, 980]
    front = [14, 346, 678, 1010]
    mid = [b + (f - b) * (FM - FB) / (FF - FB) for b, f in zip(back, front)]
    wheat_masks = []
    for k in range(3):
        bq = [(back[k], FB), (back[k + 1], FB), (mid[k + 1], FM), (mid[k], FM)]
        fq = [(mid[k], FM), (mid[k + 1], FM), (front[k + 1], FF), (front[k], FF)]
        for q, kind, (y0, y1), s0 in ((bq, "CWP"[k], (FB, FM), 0.4), (fq, "WCW"[k], (FM, FF), 0.7)):
            if kind == "W":
                m = ic.poly_mask(q)
                wheat_top(ic, m, y0, y1, min(p[0] for p in q), max(p[0] for p in q), step=18, s0=s0)
                wheat_masks.append(m)
            elif kind == "C":
                clover(ic, q, y0, y1)
            else:
                peas(ic, q, y0, y1)
    field = ic.poly_mask([(back[0], FB), (back[-1], FB), (front[-1], FF), (front[0], FF)])
    ic.shade(ic.intersect(field, ic.mask("rectangle", (0, FB, SIZE, FB + 70))), (230, 214, 170), 0.2, blur=24)
    ic.poly([(front[0], FF), (front[-1], FF), (front[-1] - 8, FF + 34), (front[0] + 8, FF + 34)], "#5e4428", "#3a2a18",
            noise=0.3, edge=3)

    # ---- barn with a gabled wagon porch, back left; clover rick, back right
    ic.shade(ic.mask("ellipse", (90, 590, 700, 660)), alpha=0.45, blur=12)
    ic.stonewall((110, 420, 660, 624), course=34)
    ic.shade(ic.mask("rectangle", (110, 420, 660, 480)), alpha=0.5, blur=12)
    for x in (150, 214, 556, 620):  # ventilation slits
        ic.rect((x - 6, 488, x + 6, 546), "#231910", "#120c06", edge=3)
    roof = [(70, 436), (700, 436), (598, 214), (172, 214)]
    ic.tiles(roof, "#8e5a3c", "#4e2e1c", course=30, stagger=40)
    weather(ic, ic.poly_mask(roof), (142, 96, 70))
    ic.rect((166, 202, 604, 222), "#6e4a32", "#4a2e1e")
    ic.shade(ic.poly_mask([(430, 200), (720, 200), (720, 450), (470, 450)]), alpha=0.22, blur=40)
    # porch: weatherboarded cheeks, open wagon doors with hay inside, gable roof
    PL, PR = 290, 490
    weatherboard(ic, (PL, 360, PR, 624), course=28)
    ic.rect((PL + 26, 430, PR - 26, 624), "#2a1c10", "#140c06", noise=0.1, edge=4)
    hay_in = [(PL + 26, 624), (PL + 40, 560), (PL + 90, 520), (PR - 60, 530), (PR - 26, 572), (PR - 26, 624)]
    ic.poly(hay_in, "#b09a58", "#5a4a22", edge=0, noise=0.35)
    ic.shade(ic.mask("rectangle", (PL + 26, 430, PR - 26, 520)), alpha=0.55, blur=10)
    for x0, x1 in ((PL - 30, PL + 26), (PR - 26, PR + 30)):  # opened door leaves
        ic.rect((x0, 440, x1, 628), "#8e6440", "#4a3020", vertical=False, noise=0.25, edge=4)
        ic.line([(x0 + 4, 490), (x1 - 4, 490)], 6, (56, 40, 24))
        ic.line([(x0 + 4, 580), (x1 - 4, 580)], 6, (56, 40, 24))
    gable = [(PL - 20, 372), (390, 250), (PR + 20, 372)]
    ic.poly([(PL, 364), (390, 262), (PR, 364)], "#9a6e46", "#5a3c22", edge=0)
    ic.line(gable, 26, (90, 60, 38))
    ic.line([(p[0], p[1] - 6) for p in gable], 8, (150, 112, 76, 180))
    ic.shade(ic.mask("rectangle", (PL, 364, PR, 400)), alpha=0.5, blur=8)

    rick(ic, 846, 650, 250, 270)

    # ---- hedgerows between the fields
    hedge(ic, [(back[0] - 10, FM - (FM - FB) * 0.02), (back[-1] + 10, FM)], 16, 16)
    for k in (1, 2):
        hedge(ic, [(back[k], FB + 8), (mid[k], FM), (front[k], FF - 10)], 12, 26)

    # ---- standing wheat along the front of the front wheat fields
    for k in (0, 2):
        wheat_stand(ic, front[k] + 8, front[k + 1] - 16, FF + 40, 220, rows=6, scale=1.15)
    ic.shade(ic.mask("rectangle", (0, FF + 10, SIZE, SIZE)), (20, 12, 4), 0.3, blur=12)
