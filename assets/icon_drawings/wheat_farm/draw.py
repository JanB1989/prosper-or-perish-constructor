"""Wheat Farm: a thatched peasant cottage at the head of open village field strips, ripe wheat.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/wheat_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/wheat_farm

Identity (tier 0 of the wheat chain): long unfenced strips of the open field running away from the
viewer, mostly golden ripe wheat with a ploughed and a green strip between them, standing wheat along
the front edge; a low thatched wattle-and-daub cottage behind, stooks of sheaves on the reaped strip.

Local helpers (shared by the four wheat tiers): ``ears`` (shaded wheat ears with awns in one layer),
``wheat_stand`` (side view of standing wheat), ``wheat_top`` (ripe field seen from above),
``stook`` (sheaves leaning together), ``furrows``, ``sprouts``, ``stubble``, ``thatch`` (from
coffee_grove).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("farming_village", "fiber_crops_farm", "free_village", "terraces")

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
    """Reaped strip: dull, darker straw stubble with faint short ticks in rows along the strip."""
    rnd = ic.random
    m = ic.poly_mask([bl, br, fr, fl])
    ic.fill(m, "#a68e5e", "#6e5a36", (bl[1], fl[1]), noise=0.3, chroma=0.08)

    def paint(dr):
        n = 7
        for k in range(1, n):
            f = k / n
            p0, p1 = lerp(bl, br, f), lerp(fl, fr, f)
            for t in np.linspace(0.02, 0.98, 30):
                x, y = lerp(p0, p1, t)
                s = 0.4 + 0.6 * t
                x += rnd.uniform(-3, 3)
                dr.line([(x, y), (x + rnd.uniform(-2, 2), y - 9 * s)], fill=(70, 56, 32, 120), width=3)
                if rnd.random() < 0.4:
                    dr.line([(x - 3, y - 1), (x - 3, y - 7 * s)], fill=(196, 180, 136, 70), width=2)

    ic.overlay(paint, m)
    return m


def stook(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Stook: sheaves of reaped wheat leaning together, tied at the waist, ears fanning at the top."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.5, base - 12, cx + w * 0.9, base + 14)), alpha=0.4, blur=8, clip=False)
    ic.shade(ic.mask("ellipse", (cx - w * 0.46, base - 7, cx + w * 0.6, base + 8)), (16, 10, 4), 0.75, blur=3,
             clip=False)  # contact shadow
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
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx + w * 0.04, 0, SIZE, SIZE))), (40, 24, 6), 0.5, blur=8)
    ic.line([(cx - w * 0.22, waist), (cx + w * 0.22, waist + 3)], 10, (120, 84, 38))
    ic.line([(cx - w * 0.2, waist - 3), (cx + w * 0.18, waist)], 3, (200, 164, 96, 180))
    items = []
    for _ in range(int(w / 9)):
        ang = -90 + rnd.uniform(-62, 62)
        a = math.radians(ang)
        d = rnd.uniform(0.1, 0.25) * h
        L = rnd.uniform(34, 44) * max(h / 220, 0.78)
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


# ---------------------------------------------------------------------------- drawing
FB, FF = 590, 930  # field back / front edge


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.86

    # ---- open field: strips running away from the viewer, grassy balks between them
    bx0, bx1, fx0, fx1 = 250, 990, 20, 1008
    kinds = ["W", "P", "W", "G", "W", "S", "W"]
    widths = [0.17, 0.09, 0.18, 0.09, 0.17, 0.21, 0.11]
    cum = np.concatenate([[0], np.cumsum(widths) / sum(widths)])
    strips = []
    for k, kind in enumerate(kinds):
        bl, br = (bx0 + (bx1 - bx0) * cum[k], FB), (bx0 + (bx1 - bx0) * cum[k + 1], FB)
        fl, fr = (fx0 + (fx1 - fx0) * cum[k], FF), (fx0 + (fx1 - fx0) * cum[k + 1], FF)
        strips.append((kind, bl, br, fl, fr))
        if kind == "W":
            m = ic.poly_mask([bl, br, fr, fl])
            wheat_top(ic, m, FB, FF, min(bl[0], fl[0]), max(br[0], fr[0]), step=18)
        elif kind == "P":
            furrows(ic, bl, br, fl, fr)
        elif kind == "G":
            sprouts(ic, bl, br, fl, fr)
        else:
            stubble(ic, bl, br, fl, fr)
    field = ic.poly_mask([(bx0, FB), (bx1, FB), (fx1, FF), (fx0, FF)])
    # each strip falls off from lit near end to darker far end, and darkens slightly towards its right edge
    for kind, bl, br, fl, fr in strips:
        sm = ic.poly_mask([bl, br, fr, fl])
        ic.shade(ic.intersect(sm, ic.mask("rectangle", (0, FB - 40, SIZE, FB + 70))), (52, 34, 12), 0.34, blur=36)
        ic.shade(ic.intersect(sm, ic.poly_mask([lerp(bl, br, 0.72), br, fr, lerp(fl, fr, 0.72)])), (60, 38, 12), 0.22,
                 blur=14)
        ic.shade(ic.intersect(sm, ic.poly_mask([bl, lerp(bl, br, 0.3), lerp(fl, fr, 0.3), fl])), (255, 236, 180),
                 0.12, blur=14)
    # dark furrow balks between neighbouring strips
    for k in range(1, len(kinds)):
        p0 = (bx0 + (bx1 - bx0) * cum[k], FB)
        p1 = (fx0 + (fx1 - fx0) * cum[k], FF)
        ic.line([p0, p1], 10, (58, 42, 20, 235))
        ic.line([(p0[0] + 1, p0[1]), (p1[0] + 2, p1[1])], 4, (34, 22, 10, 220))
    # light haze only at the very back edge
    ic.shade(ic.intersect(field, ic.mask("rectangle", (0, FB, SIZE, FB + 30))), (230, 214, 170), 0.12, blur=16)
    # earth lip along the front edge
    ic.poly([(fx0, FF), (fx1, FF), (fx1 - 8, FF + 34), (fx0 + 8, FF + 34)], "#5e4428", "#3a2a18", noise=0.3, edge=3)

    # ---- cottage at the head of the field
    ic.shade(ic.mask("ellipse", (40, 580, 640, 680)), alpha=0.4, blur=16, clip=False)
    ic.poly([(30, 640), (160, 560), (660, 560), (620, 660), (60, 672)], "#6e5a38", "#4e3e26", noise=0.3, edge=0)
    daub(ic, (96, 426, 560, 640), posts=(102, 280, 440, 554))
    ic.door(170, 506, 244, 640, arched=False, surround=None)
    ic.window(338, 494, 394, 540)
    ic.shade(ic.mask("rectangle", (96, 426, 560, 486)), alpha=0.5, blur=12)
    ridge = [(196, 214), (330, 204), (462, 212)]
    eave = [(x, 446 + rnd.uniform(-5, 7)) for x in np.linspace(40, 620, 20)]
    thatch(ic, ridge, eave)
    ic.rect((392, 164, 434, 226), "#8a7a66", "#56483a", edge=4)  # smoke hole hood
    ic.shade(ic.poly_mask([(380, 200), (660, 200), (660, 480), (420, 480)]), alpha=0.2, blur=40)
    for x in (608, 646, 684):  # hurdle fence stub
        ic.rect((x - 8, 556, x + 8, 648), "#8a6848", "#4a3222", vertical=False, edge=3)
    ic.line([(600, 582), (692, 586)], 9, (120, 90, 58))
    ic.line([(600, 618), (692, 622)], 9, (110, 82, 52))

    # ---- stooks on the reaped strip
    _, bl, br, fl, fr = strips[5]
    for t, dx, h, w in ((0.1, 22, 112, 118), (0.47, -24, 124, 132), (0.86, 18, 136, 146)):
        cx, base = lerp(lerp(bl, br, 0.5), lerp(fl, fr, 0.5), t)
        stook(ic, cx + dx, base, h, w)

    # ---- standing wheat along the front edge of the wheat strips
    for kind, bl, br, fl, fr in strips:
        if kind == "W":
            wheat_stand(ic, fl[0] + 4, fr[0] - 4, FF + 40, 240, rows=6, scale=1.15)
    # ploughed strip and sprouts show their front ends
    ic.shade(ic.mask("rectangle", (0, FF + 10, SIZE, SIZE)), (20, 12, 4), 0.3, blur=12)
