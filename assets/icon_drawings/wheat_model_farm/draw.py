"""Wheat Model Farm: a Georgian brick farmhouse and barn above a large drilled field, a horse seed drill.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/wheat_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/wheat_model_farm

Identity (tier 3 of the wheat chain): one large surveyed field ruled into straight drill rows,
golden ripe wheat on the left and a wide freshly drilled brown strip on the right with a low seed drill
at its right end (narrow seed hopper between two small spoked wheels, a row of light-caught coulter
tubes angled into the soil); a surveyor's ranging pole;
behind, a symmetrical brick farmhouse with sash windows, a pedimented door and a hipped slate roof,
and a brick barn wing.

Helpers shared by the four wheat tiers: ``ears``, ``wheat_stand``, ``wheat_top``, ``stook``,
``furrows``, ``sprouts``, ``stubble``, ``thatch``, ``daub``; local to this tier: ``weather``,
``bricks``, ``sash``, ``wheel``, ``drill``, ``ranging_pole``.
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("farming_village", "fiber_crops_farm", "windmill", "burgher_mansion")

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
        col = rnd.choice(((150, 150, 110), (30, 30, 34), (200, 200, 190)))
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - r * 1.6, y - r * 0.6, x + r * 1.6, y + r * 0.6))), col, 0.2,
                 blur=6)


def bricks(ic: Icon, box, base=("#a4603e", "#6e3a24"), course: float = 18) -> None:
    """Brick wall: warm gradient, per-brick tone, thin pale mortar courses in stretcher bond."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, base[0], base[1], noise=0.25, edge=0)
    m = ic.mask("rectangle", box)

    def paint(dr):
        y, k = y0, 0
        while y < y1:
            x = x0 - (22 if k % 2 else 0)
            while x < x1:
                w = 44
                t = rnd.uniform(-1, 1)
                if abs(t) > 0.4:
                    col = (255, 220, 190, int(40 * abs(t))) if t > 0 else (30, 10, 4, int(60 * abs(t)))
                    dr.rectangle((x, y, x + w, y + course), fill=col)
                dr.line([(x, y), (x, y + course)], fill=(206, 186, 160, 90), width=2)
                x += w
            dr.line([(x0, y), (x1, y)], fill=(206, 186, 160, 110), width=3)
            y += course
            k += 1

    ic.overlay(paint, m)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def sash(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Georgian sash window: pale stone lintel and sill, white frame, dark panes with glazing bars."""
    ic.rect((x0 - 10, y0 - 16, x1 + 10, y0 - 2), "#d8ccb4", "#a89c86", edge=3)
    ic.rect((x0 - 8, y1, x1 + 8, y1 + 10), "#d8ccb4", "#a89c86", edge=3)
    ic.rect((x0, y0, x1, y1), "#d6d0c2", "#a8a294", edge=3)
    ic.rect((x0 + 6, y0 + 6, x1 - 6, y1 - 6), "#3a3a3e", "#1c1b1e", noise=0.08, edge=0)
    ic.shade(ic.poly_mask([(x0 + 6, y0 + 6), (x1 - 6, y0 + 6), (x0 + 6, (y0 + y1) / 2)]), (160, 170, 185), 0.2)
    ic.line([((x0 + x1) / 2, y0 + 6), ((x0 + x1) / 2, y1 - 6)], 4, (214, 208, 196))
    for f in (0.36, 0.64):
        y = y0 + (y1 - y0) * f
        ic.line([(x0 + 6, y), (x1 - 6, y)], 4, (214, 208, 196))


def wheel(ic: Icon, cx: float, cy: float, r: float, spokes: int = 10, behind=("#6e5236", "#4a3622")) -> None:
    """Spoked wooden wheel with an iron tyre, seen nearly face on (lit upper left)."""
    rx = r * 0.86
    ic.fill(ic.mask("ellipse", (cx - rx, cy - r, cx + rx, cy + r)), "#4a4a4c", "#1e1e20", noise=0.15)
    ic.fill(ic.mask("ellipse", (cx - rx + 8, cy - r + 8, cx + rx - 8, cy + r - 8)), "#9a7048", "#4e3420",
            radial=(cx - rx, cy - r, r * 2), noise=0.2)
    hole = ic.mask("ellipse", (cx - rx + 22, cy - r + 22, cx + rx - 22, cy + r - 22))
    ic.fill(hole, behind[0], behind[1], (cy - r, cy + r), noise=0.3)  # soil seen between the spokes
    ic.shade(hole, alpha=0.25, blur=8)
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        p1 = (cx + math.cos(a) * (rx - 16), cy + math.sin(a) * (r - 16))
        ic.line([(cx, cy), p1], max(6, int(12 * r / 92)), (60, 40, 24))
        ic.line([(cx - 1, cy - 1), (p1[0] - 1, p1[1] - 1)], max(3, int(6 * r / 92)), (150, 110, 70))
    k = max(12, 18 * r / 92)
    ic.ellipse((cx - k, cy - k * 1.1, cx + k, cy + k * 1.1), "#6a6a6c", "#2a2a2c", edge=3)


def drill(ic: Icon, x0: float, x1: float, ground: float) -> None:
    """Seed drill, low and side-on: small spoked wheels at each end, a narrow seed hopper on the axle
    frame between them, and a dominant row of thin light-caught coulter tubes angled down into the soil,
    each casting a small shadow; a short shaft forward to the left."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (x0 - 30, ground - 12, x1 + 40, ground + 18)), alpha=0.4, blur=10)
    r = 64
    wy = ground - r
    ic.beam((x0 + 40, wy + 4), (x0 - 120, wy + 40), 12, (132, 96, 62))  # shaft
    wheel(ic, x0 + 34, wy, r)
    # frame on the axle
    ic.beam((x0 + 20, wy - 4), (x1 - 20, wy - 4), 14, (110, 78, 48))
    # coulter tubes: from the hopper foot down and forward into the soil
    tubes = np.linspace(x0 + 86, x1 - 70, 7)
    ht, hb = wy - 96, wy - 44  # hopper top / bottom
    for x in tubes:
        x = x + rnd.uniform(-3, 3)
        top, tip = (x + 6, hb - 4), (x - 30, ground + 2)
        ic.line([(top[0] + 14, ground + 2), (tip[0] + 22, ground + 6)], 8, (20, 12, 4, 120))  # cast shadow
        ic.line([top, tip], 10, (44, 44, 48))
        ic.line([(top[0] - 3, top[1]), (tip[0] - 3, tip[1] - 2)], 4, (214, 214, 206))
        ic.poly([(tip[0] - 10, tip[1] - 12), (tip[0] + 8, tip[1] - 12), (tip[0] + 2, tip[1] + 6),
                 (tip[0] - 12, tip[1] + 4)], "#8a8a8e", "#3a3a3e", edge=3)  # coulter shoe cutting the soil
        ic.line([(tip[0] - 16, tip[1] + 4), (tip[0] + 10, tip[1] + 4)], 4, (40, 26, 12, 180))  # slit in the soil
    # narrow hopper box, a little wider at the top, lid propped, seed showing
    box = [(x0 + 70, ht), (x1 - 56, ht), (x1 - 70, hb), (x0 + 84, hb)]
    ic.poly(box, "#a87c52", "#5e4028", edge=4)
    ic.line([(x0 + 80, (ht + hb) / 2), (x1 - 66, (ht + hb) / 2)], 3, (60, 40, 22, 120))
    ic.shade(ic.intersect(ic.poly_mask(box), ic.mask("rectangle", (0, ht, SIZE, ht + 14))), (255, 236, 200), 0.3)
    ic.shade(ic.intersect(ic.poly_mask(box), ic.mask("rectangle", (0, hb - 20, SIZE, SIZE))), alpha=0.3, blur=6)
    top = [(x0 + 70, ht), (x1 - 56, ht), (x1 - 70, ht - 16), (x0 + 84, ht - 16)]
    ic.poly(top, "#e0b050", "#9a6a24", edge=3, noise=0.35)
    seeds = [(rnd.uniform(x0 + 90, x1 - 76), rnd.uniform(ht - 14, ht - 2), 9, 4, rnd.uniform(-30, 30),
              rnd.uniform(0.9, 1.1)) for _ in range(34)]
    ears(ic, seeds, ic.poly_mask(top))
    lid = [(x0 + 84, ht - 16), (x1 - 70, ht - 16), (x1 - 84, ht - 50), (x0 + 98, ht - 50)]
    ic.poly(lid, "#8a6240", "#5a3c24", edge=4)
    wheel(ic, x1 - 30, wy, r)


def ranging_pole(ic: Icon, x: float, top: float, base: float) -> None:
    """Surveyor's ranging pole: red and white bands, a small pennant."""
    n = 6
    for k in range(n):
        y0 = top + (base - top) * k / n
        y1 = top + (base - top) * (k + 1) / n
        ic.rect((x - 7, y0, x + 7, y1), "#e8e0d0" if k % 2 else "#b43a2a", "#b8b0a0" if k % 2 else "#7a2418", edge=0)
    ic.outline([(x - 7, top), (x + 7, top), (x + 7, base), (x - 7, base)], 3)
    ic.poly([(x + 7, top), (x + 56, top + 16), (x + 7, top + 32)], "#c44a30", "#8a2a1a", edge=3)


# ---------------------------------------------------------------------------- drawing
FB, FF = 610, 930


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.80

    # ---- one large surveyed field: drilled wheat, and a freshly drilled strip on the right
    bx0, bx1, fx0, fx1 = 40, 990, 12, 1012
    split_b, split_f = 560, 430
    whe = [(bx0, FB), (split_b, FB), (split_f, FF), (fx0, FF)]
    soil = [(split_b, FB), (bx1, FB), (fx1, FF), (split_f, FF)]
    wm = ic.poly_mask(whe)
    wheat_top(ic, wm, FB, FF, fx0, split_b, step=18, s0=0.45)
    sm = ic.poly_mask(soil)
    ic.fill(sm, "#8a6440", "#4e3620", (FB, FF), noise=0.34, chroma=0.1)
    for _ in range(40):  # clods and damp patches in the fresh soil
        x, y = rnd.uniform(split_f, fx1), rnd.uniform(FB + 10, FF - 10)
        r = rnd.uniform(10, 26) * (0.5 + 0.5 * (y - FB) / (FF - FB))
        ic.shade(ic.intersect(sm, ic.mask("ellipse", (x - r * 1.8, y - r * 0.6, x + r * 1.8, y + r * 0.6))),
                 (220, 190, 140) if rnd.random() < 0.5 else (30, 18, 8), 0.14, blur=5)
    vx, vy = 520, -900  # vanishing point of the drill rows

    def rows(dr, color, width, n, x_from, x_to):
        for k in range(n + 1):
            xf = x_from + (x_to - x_from) * k / n
            t = (FB - vy) / (FF - vy)
            xb = vx + (xf - vx) * t
            dr.line([(xb, FB), (xf, FF)], fill=color, width=width)

    # drilled wheat: alternate darker and lighter rows so the straight rows survive at game size
    sp = (fx1 + 60 - fx0) / 22
    ic.overlay(lambda d: rows(d, (66, 40, 12, 170), 9, 11, fx0, fx1 + 60), wm)
    ic.overlay(lambda d: rows(d, (86, 56, 18, 110), 6, 11, fx0 + sp, fx1 + 60 + sp), wm)
    ic.overlay(lambda d: rows(d, (250, 214, 136, 80), 7, 22, fx0 + sp * 0.5, fx1 + 60 + sp * 0.5), wm)
    # fresh soil: dark drill slits, lit ridges, faint seed lines
    ic.overlay(lambda d: rows(d, (44, 28, 12, 130), 5, 22, fx0, fx1 + 60), sm)
    ic.overlay(lambda d: rows(d, (190, 156, 110, 55), 4, 22, fx0 + 12, fx1 + 72), sm)

    def seed_dots(dr):
        for k in range(23):
            xf = fx0 + (fx1 + 60 - fx0) * k / 22 + 4
            xb = vx + (xf - vx) * (FB - vy) / (FF - vy)
            for t in np.linspace(0.03, 0.97, 18):
                x, y = xb + (xf - xb) * t + rnd.uniform(-1, 1), FB + (FF - FB) * t
                q = 1.5 + 2 * t
                dr.ellipse((x - q, y - q * 0.6, x + q, y + q * 0.6), fill=(226, 200, 140, 110))

    ic.overlay(seed_dots, sm)
    field = ic.poly_mask([(bx0, FB), (bx1, FB), (fx1, FF), (fx0, FF)])
    ic.shade(ic.intersect(field, ic.mask("rectangle", (0, FB, SIZE, FB + 70))), (230, 214, 170), 0.2, blur=24)
    ic.poly([(fx0, FF), (fx1, FF), (fx1 - 8, FF + 34), (fx0 + 8, FF + 34)], "#5e4428", "#3a2a18", noise=0.3, edge=3)

    # ---- barn wing, right: brick with a slate roof and a cart arch
    ic.shade(ic.mask("ellipse", (520, 590, 980, 650)), alpha=0.45, blur=12)
    bricks(ic, (556, 470, 950, 626))
    ic.door(700, 520, 800, 626, arched=True, surround="#d0c4ac")
    for x in (610, 880):
        ic.rect((x - 8, 506, x + 8, 560), "#2a1c10", "#140c06", edge=3)
    ic.shade(ic.mask("rectangle", (556, 470, 950, 516)), alpha=0.5, blur=10)
    wroof = [(530, 484), (976, 484), (930, 360), (576, 360)]
    ic.tiles(wroof, "#7a8088", "#3e434a", course=22, stagger=34)
    weather(ic, ic.poly_mask(wroof), (110, 116, 124), 14)

    # ---- farmhouse, left: symmetrical brick front, sash windows, pedimented door, hipped slate roof
    ic.shade(ic.mask("ellipse", (50, 600, 600, 660)), alpha=0.45, blur=12)
    for x in (150, 490):  # chimneys at the ridge ends
        ic.rect((x - 26, 170, x + 26, 290), "#9a5a3c", "#5e3222", edge=4)
        ic.rect((x - 32, 160, x + 32, 180), "#b4a48c", "#7e7262", edge=3)
        for dx in (-12, 12):
            ic.rect((x + dx - 7, 142, x + dx + 7, 162), "#8a5a3c", "#5a3422", edge=3)
    bricks(ic, (84, 388, 556, 630))
    ic.rect((78, 382, 562, 398), "#d8ccb4", "#a89c86", edge=3)  # cornice
    for x in (84, 548):  # quoins
        for k, y in enumerate(range(398, 630, 38)):
            w = 26 if k % 2 else 18
            ic.rect((x - (0 if x < 300 else w - 8), y, x + (w if x < 300 else 8), y + 34), "#d6cab2", "#a4987f", edge=3)
    for x in (130, 220, 420, 510):
        sash(ic, x - 26, 424, x + 26, 486)
        sash(ic, x - 26, 532, x + 26, 594)
    ic.door(292, 516, 348, 630, arched=False, surround="#d0c4ac")
    ic.poly([(276, 510), (364, 510), (320, 470)], "#d8ccb4", "#a89c86", edge=4)  # pediment
    sash(ic, 294, 424, 346, 486)
    ic.shade(ic.mask("rectangle", (84, 398, 556, 440)), alpha=0.45, blur=10)
    ic.shade(ic.mask("rectangle", (84, 600, 556, 630)), (40, 40, 20), 0.35, blur=8)
    hroof = [(58, 400), (582, 400), (480, 250), (160, 250)]
    ic.tiles(hroof, "#848a92", "#40454c", course=22, stagger=34)
    weather(ic, ic.poly_mask(hroof), (116, 122, 130), 20)
    ic.line([(160, 250), (480, 250)], 12, (70, 74, 80))
    ic.shade(ic.poly_mask([(380, 240), (600, 240), (600, 410), (420, 410)]), alpha=0.2, blur=40)

    # ---- surveyor's pole in the field, seed drill on the freshly drilled strip
    ranging_pole(ic, 640, 520, 700)
    drill(ic, 700, 994, 900)

    # ---- standing wheat along the front of the drilled wheat, in rows
    wheat_stand(ic, fx0 + 6, split_f - 20, FF + 40, 170, rows=4, scale=1.1)
    ic.shade(ic.mask("rectangle", (0, FF + 10, SIZE, SIZE)), (20, 12, 4), 0.3, blur=12)
