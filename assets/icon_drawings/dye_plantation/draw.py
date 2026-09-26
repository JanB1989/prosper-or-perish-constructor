"""Dye Plantation: rows of indigo bushes behind stepped masonry steeping and beating vats of blue
dye liquor, a thatched drying shed with indigo cakes and hanging cut plants.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/dye_plantation/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/dye_plantation

Identity: the deep indigo blue of the beating vat (coppery froth, paddles) and the green steeping
vat above it, set against blue-green indigo bushes with pink flower spikes; the drying shed with
dark blue cakes on its shelves at the right, a basket of cut plants at the bottom left.

Local helpers: ``tint``, ``stones`` (from cookshop), ``thatch`` (from coffee_grove), ``bush``
(leafy indigo shrub from many small leaflets in one layer, flower spikes), ``vat`` (masonry tank
seen from the raised camera: coping, inner wall, liquid, front wall), ``froth``, ``cakes`` (row of
indigo cakes on a board).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("dyesworks", "fiber_crops_farm", "cotton_plantation", "farming_village")

INDIGO = ("#2e50a4", "#0e1a4a")
STEEP = ("#948a44", "#3e3a18")
LEAFLET = ((78, 110, 72), (118, 148, 100), (22, 36, 22))
LEAFLET2 = ((58, 86, 58), (90, 118, 82), (18, 30, 18))


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form (from cookshop)."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.8, 1.15)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.2, 2.5)
            j = lambda: rnd(-3, 3)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 55)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=5)
            x += w
        y += h
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def thatch(ic: Icon, ridge, eave, c=("#b8a06a", "#6c5632")) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave (from coffee_grove)."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.26, 0.5, 0.74, 1.0]
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
        tint_ = rnd.uniform(0.92, 1.06)
        ic.fill(band, tuple(int(v * tint_) for v in rgb(c[0])), tuple(int(v * tint_) for v in rgb(c[1])),
                (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

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


def leaflets(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Small oval leaflets (x, y, r, angle, palette) in one blended layer: dark rim, body, lit edge."""

    def paint(dr):
        for x, y, r, a, (mid, lit, dk) in items:
            c, s = math.cos(a), math.sin(a)

            def oval(sc, dx=0.0, dy=0.0):
                return [(x + dx + (math.cos(t) * r * sc) * c - (math.sin(t) * r * 0.5 * sc) * s,
                         y + dy + (math.cos(t) * r * sc) * s + (math.sin(t) * r * 0.5 * sc) * c)
                        for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]

            dr.polygon(oval(1.12, 1, 2), fill=dk + (230,))
            dr.polygon(oval(1.0), fill=mid + (255,))
            dr.polygon(oval(0.55, -r * 0.25, -r * 0.22), fill=lit + (170,))

    ic.overlay(paint, clip)


def bush(ic: Icon, cx: float, base: float, w: float, h: float, flowers: int = 4, tone: float = 1.0) -> Image.Image:
    """Indigo shrub: woody stems, a shaded mass of small pinnate leaflets lit from the upper left,
    thin pink flower spikes on top. Returns the bush mask."""
    rnd = ic.random
    for dx in (-0.2, 0.05, 0.25):
        ic.line([(cx + dx * w * 0.3, base), (cx + dx * w, base - h * 0.6)], 7, (70, 52, 36))
    # the crown: overlapping clumps, each lit from the upper left, then fine leaf dabs
    m = Image.new("L", (SIZE, SIZE), 0)
    clumps = []
    for _ in range(9):
        u = rnd.uniform(-0.75, 0.75)
        cy = base - h * rnd.uniform(0.3, 0.72) + abs(u) * h * 0.12
        clumps.append((cx + u * w * 0.5, cy, w * rnd.uniform(0.2, 0.3)))
    clumps.append((cx, base - h * 0.78, w * 0.26))
    clumps.sort(key=lambda c: c[1])
    g = tuple(int(v * tone) for v in (84, 116, 78))
    for bx, by, br in clumps:
        bm = ic.poly_mask(ic.jitter(bx, min(by, base - br * 0.9), br * 1.15, br, 20, 0.1))
        ic.fill(bm, g, (14, 26, 16), radial=(bx - br * 0.8, by - br * 0.9, br * 2.4), noise=0.26, chroma=0.1)
        m = union(m, bm)
    x0, x1, y0, y1 = cx - w * 0.6, cx + w * 0.6, base - h, base

    def dabs(dr):
        for _ in range(int(w * h / 60)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            v = (y - y0) / h + (x - cx) / w * 0.6
            r = rnd.uniform(4, 7)
            col = (150, 182, 130, 80) if rnd.random() < 0.7 - v else (12, 24, 12, 80)
            dr.ellipse((x - r, y - r * 0.55, x + r, y + r * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - h * 0.3, SIZE, SIZE))), (8, 16, 8), 0.35, blur=16)
    for _ in range(flowers):
        x = cx + rnd.uniform(-w * 0.35, w * 0.35)
        y = base - h * rnd.uniform(0.8, 0.98)
        L = rnd.uniform(22, 32)
        ang = math.radians(-90 + rnd.uniform(-25, 25))
        tip = (x + math.cos(ang) * L, y + math.sin(ang) * L)
        ic.line([(x, y), tip], 4, (70, 60, 40))
        dots = [(x + (tip[0] - x) * t + rnd.uniform(-4, 4), y + (tip[1] - y) * t, rnd.uniform(4, 6),
                 0, ((176, 96, 120), (220, 150, 166), (96, 44, 64))) for t in np.linspace(0.35, 1, 5)]
        leaflets(ic, dots)
    return m


def spikes(ic: Icon, items) -> None:
    """Small upright pink flower spikes (x, y, length): a tapering raceme, lit on the left, on a short stem."""

    def paint(dr):
        for x, y, L in items:
            dr.line([(x, y + 8), (x, y)], fill=(60, 70, 40, 255), width=3)
            w = L * 0.2
            dr.polygon([(x - w, y), (x + w, y), (x + 1.5, y - L), (x - 1.5, y - L)], fill=(120, 58, 84, 255))
            dr.polygon([(x - w * 0.8, y - 2), (x, y - 2), (x - 0.5, y - L + 3)], fill=(214, 140, 164, 255))
            for k in range(3):
                yy = y - L * (0.25 + 0.25 * k)
                dr.line([(x - w * 0.9, yy), (x + w * 0.9, yy - 2)], fill=(90, 40, 60, 160), width=2)

    ic.overlay(paint)


def field_row(ic: Icon, x0: float, x1: float, b0: float, b1: float, r: float, tone: float = 1.0,
              flowers: int = 6) -> Image.Image:
    """One row of indigo seen from the raised camera, its foot running from (x0, b0) to (x1, b1):
    separate bushy crowns of different sizes and heights lit from the upper left, fine leaf dabs, a
    shadowed foot, small upright pink flower spikes. Returns the row mask."""
    rnd = ic.random
    m = Image.new("L", (SIZE, SIZE), 0)
    g = tuple(int(v * tone) for v in (84, 116, 78))

    def base_at(x):
        return b0 + (b1 - b0) * (x - x0) / max(x1 - x0, 1)

    x = x0
    crowns = []
    while x < x1:
        rr = r * rnd.uniform(0.66, 1.28)
        crowns.append((x, base_at(x) - rr * rnd.uniform(0.6, 1.7), rr))
        x += rr * rnd.uniform(1.0, 1.45)
    low = [(x, base_at(x) + rnd.uniform(-8, 10)) for x in np.linspace(x1 + r * 0.5, x0 - r * 0.6, 18)]
    foot = ic.poly_mask([(x0 - r * 0.6, b0 - r * 0.7), (x1 + r * 0.5, b1 - r * 0.7)] + low)
    ic.shade(ic.poly_mask([(x0, b0 - 4), (x1, b1 - 4), (x1, b1 + 26), (x0, b0 + 26)]), (20, 12, 6), 0.35, blur=10)
    ic.fill(foot, tuple(int(v * 0.5) for v in g), (10, 18, 10), (min(b0, b1) - r, max(b0, b1)), noise=0.3)
    m = union(m, foot)
    for bx, by, br in crowns:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.05, br * 0.9, 20, 0.1))
        ic.fill(bm, g, (14, 26, 16), radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.26, chroma=0.1)
        ic.shade(ic.intersect(bm, ic.mask("ellipse", (bx - br * 0.2, by - br * 0.1, bx + br * 1.3, by + br * 1.2))),
                 (6, 14, 6), 0.3, blur=8)
        m = union(m, bm)
    y0 = min(c[1] - c[2] for c in crowns)
    y1 = max(b0, b1)

    def dabs(dr):
        for _ in range(int((x1 - x0 + 2 * r) * (y1 - y0) / 55)):
            x, y = rnd.uniform(x0 - r, x1 + r), rnd.uniform(y0, y1)
            v = (y - y0) / (y1 - y0)
            rr = rnd.uniform(4, 7)
            col = (150, 182, 130, 80) if rnd.random() < 0.75 - v else (12, 24, 12, 80)
            dr.ellipse((x - rr, y - rr * 0.55, x + rr, y + rr * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.poly_mask([(0, b0 - r * 0.5), (SIZE, b1 - r * 0.5 + (b1 - b0) * 0.4), (SIZE, SIZE), (0, SIZE)])),
             (8, 16, 8), 0.4, blur=14)
    items = []
    for _ in range(flowers):
        bx, by, br = rnd.choice(crowns)
        items.append((bx + rnd.uniform(-br * 0.5, br * 0.5), by - br * rnd.uniform(0.35, 0.7), rnd.uniform(20, 28)))
    spikes(ic, sorted(items, key=lambda it: it[1]))
    return m


def vat(ic: Icon, x0: float, x1: float, rim: float, bottom: float, depth: float, liquid, rim_w: float = 20,
        wall=("#9c8a6e", "#62523e")) -> tuple[Image.Image, list]:
    """Masonry tank seen from the raised camera: front wall down to ``bottom``, coping around the top
    whose back edge is ``depth`` above the front edge, inner back wall, liquid surface.
    Returns the liquid mask and its polygon."""
    ins = depth * 0.35
    outer = [(x0, rim), (x1, rim), (x1 - ins, rim - depth), (x0 + ins, rim - depth)]
    stones(ic, (x0, rim, x1, bottom), wall[0], wall[1], course=28)
    ic.shade(ic.mask("rectangle", (x0, bottom - 50, x1, bottom)), (30, 24, 14), 0.3, blur=14)
    ic.outline([(x0, rim), (x1, rim), (x1, bottom), (x0, bottom)], 5)
    ic.poly(outer, "#c4b494", "#94866c", edge=5)
    inner = [(x0 + rim_w, rim - rim_w * 0.6), (x1 - rim_w, rim - rim_w * 0.6), (x1 - ins - rim_w * 0.8, rim - depth + rim_w * 0.5),
             (x0 + ins + rim_w * 0.8, rim - depth + rim_w * 0.5)]
    im = ic.poly_mask(inner)
    ic.fill(im, "#5a5040", "#2a241c", (inner[2][1], inner[0][1]), noise=0.2)  # inner walls in shade
    surf = [(p[0] + (4 if i in (0, 3) else -4), p[1] + (18 if i in (2, 3) else -2)) for i, p in enumerate(inner)]
    sm = ic.poly_mask(surf)
    ic.fill(sm, liquid[0], liquid[1], (surf[2][1], surf[0][1]), noise=0.14, chroma=0.06)
    tint(ic, ic.mask("rectangle", (0, surf[2][1], SIZE, surf[2][1] + 16)), sm, (0, 0, 0), 0.4, 5)
    # a pale sky reflection streak and a stained tide line on the coping
    ic.line([(surf[3][0] + 30, surf[3][1] + 12), (surf[2][0] - 60, surf[2][1] + 14)], 5, (220, 230, 240, 70))
    ic.outline(inner, 4, (40, 30, 20, 180))
    ic.line([(x0 + rim_w, rim - rim_w * 0.6 + 3), (x1 - rim_w, rim - rim_w * 0.6 + 3)], 5, (40, 60, 110, 90))
    return sm, surf


def froth(ic: Icon, clip: Image.Image, centres, n: int = 26, spread: float = 70) -> None:
    """Pale blue-white foam gathered in clusters round the paddles of beaten indigo liquor: a few
    big bubbles in the middle of each cluster, smaller ones round its edge, a rare coppery sheen."""
    rnd = ic.random
    items = []
    for cx, cy in centres:
        for _ in range(n):
            dx, dy = rnd.gauss(0, spread), rnd.gauss(0, spread * 0.32)
            d = min(1.0, math.hypot(dx / spread, dy / (spread * 0.32)) / 2.2)
            r = rnd.uniform(6, 13) * (1.25 - 0.8 * d)
            pal = ((132, 152, 200), (196, 210, 236), (44, 60, 124)) if rnd.random() < 0.94 else \
                ((168, 130, 120), (214, 180, 160), (80, 60, 70))
            items.append((cx + dx, cy + dy, r, rnd.uniform(-0.3, 0.3), pal))
    items.sort(key=lambda it: it[1])
    leaflets(ic, items, clip)


def cakes(ic: Icon, x0: float, x1: float, y: float, s: float = 30) -> None:
    """Row of dark blue indigo cakes on a board: small cubes with a lit top face and a coppery bloom."""
    rnd = ic.random
    ic.rect((x0 - 10, y, x1 + 10, y + 14), "#8e6a46", "#4e3420", edge=4)
    x = x0
    while x + s < x1:
        h = s * rnd.uniform(0.8, 1.0)
        ic.rect((x, y - h, x + s, y), "#2e3e6e", "#141c38", vertical=False, noise=0.2, edge=3)
        ic.poly([(x, y - h), (x + s, y - h), (x + s + 8, y - h - 8), (x + 8, y - h - 8)], "#5a6a9a", "#3a4a78", edge=3)
        if rnd.random() < 0.4:
            ic.shade(ic.mask("rectangle", (x + 4, y - h + 4, x + s - 6, y - h + 12)), (180, 120, 110), 0.3)
        x += s + rnd.uniform(4, 8)


def cut_plant(ic: Icon, x: float, y: float, L: float, ang: float) -> None:
    """A cut indigo stem lying or hanging: a thin stalk set with leaflets."""
    rnd = ic.random
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    ic.line([(x, y), (x + c * L, y + s * L)], 5, (70, 56, 36))
    items = []
    for t in np.linspace(0.15, 1, 7):
        px, py = x + c * L * t, y + s * L * t
        for sg in (-1, 1):
            items.append((px - s * sg * 10, py + c * sg * 10, 9, math.radians(ang) + sg * 0.8, LEAFLET2))
    leaflets(ic, items)


def shed(ic: Icon) -> None:
    """Open thatched drying shed, right: posts, shelves of indigo cakes, cut plants hung to wilt."""
    rnd = ic.random
    L, R, TOP, BASE = 640, 976, 470, 800
    ic.rect((L, TOP, R, BASE), "#35281c", "#17110b", edge=0)

    def slats(dr):
        for x in np.arange(L + 10, R, 28):
            dr.line([(x + rnd.uniform(-3, 3), TOP), (x, BASE)], fill=(90, 70, 50, 60), width=4)

    ic.overlay(slats)
    # hanging bunches of cut indigo along a pole
    ic.beam((L + 10, TOP + 40), (R - 10, TOP + 40), 12, (96, 66, 42))
    for x in np.linspace(L + 40, R - 40, 6):
        for k in range(3):
            cut_plant(ic, x + rnd.uniform(-4, 4), TOP + 44, rnd.uniform(70, 100), 90 + (k - 1) * 14)
        ic.ellipse((x - 9, TOP + 36, x + 9, TOP + 52), "#6a5236", "#3e2e1c", edge=3)
    cakes(ic, L + 30, R - 30, TOP + 196, 30)
    cakes(ic, L + 30, R - 30, TOP + 286, 30)
    ic.shade(ic.mask("rectangle", (L, TOP, R, TOP + 80)), alpha=0.45, blur=14)
    for x in (L + 10, (L + R) / 2, R - 10):
        ic.rect((x - 12, TOP, x + 12, BASE), "#8a6442", "#4a3220", vertical=False, edge=3)
    ic.outline([(L, TOP), (R, TOP), (R, BASE), (L, BASE)])
    ridge = [(684, 200), (806, 192), (936, 198)]
    eave = [(x, 488 + rnd.uniform(-5, 7)) for x in np.linspace(612, 1004, 16)]
    thatch(ic, ridge, eave)
    ic.shade(ic.poly_mask([(840, 300), (1030, 300), (1030, 520), (860, 520)]), alpha=0.18, blur=50)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.84

    # indigo field: three receding rows with soil between them, the back row rising towards the shed
    soil = [(84, 366), (250, 344), (700, 296), (700, 800), (70, 800), (60, 640), (74, 520)]
    ic.poly(soil, "#6e5438", "#4a3624", noise=0.34, edge=0)
    for k, (b0, b1, r, x0, x1) in enumerate(((410, 340, 42, 64, 640), (530, 482, 52, 44, 640), (656, 628, 62, 50, 620))):
        ic.shade(ic.poly_mask([(0, b0 + 4), (SIZE, b1 + 4 + (b1 - b0) * 0.4), (SIZE, b1 + 40), (0, b0 + 40)]),
                 (255, 236, 200), 0.12, blur=8)  # a lit strip of bare soil in front of the row
        field_row(ic, x0, x1, b0, b1, r, tone=0.8 + 0.12 * k, flowers=6 + 2 * k)
    shed(ic)

    # yard
    top = [(40, 900)] + [(x, 880 + rnd.uniform(-8, 8)) for x in np.linspace(100, 940, 10)] + [(1000, 900)]
    ic.poly(top + [(1006, 990), (520, 1000), (24, 992)], "#86684a", "#56422e", noise=0.34, edge=3)

    # steeping vat (upper): murky yellow-green liquor, cut plants weighted down under a cross beam
    sm, surf = vat(ic, 50, 450, 770, 900, 130, STEEP)
    y_top, y_bot = surf[3][1], surf[0][1]

    def stems(dr):
        for _ in range(26):
            x = rnd.uniform(surf[3][0] + 10, surf[2][0] - 20)
            y = rnd.uniform(y_top + 6, y_bot - 4)
            L = rnd.uniform(40, 90)
            a = math.radians(rnd.uniform(-25, 25) + rnd.choice((0, 180)))
            p1 = (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)
            dr.line([(x, y), p1], fill=(52, 60, 22, 220), width=5)
            for t in (0.3, 0.55, 0.8):
                px, py = x + (p1[0] - x) * t, y + (p1[1] - y) * t
                dr.ellipse((px - 7, py - 4, px + 7, py + 4), fill=(66, 82, 34, 200))

    ic.overlay(stems, sm)
    ic.shade(sm, (118, 112, 44), 0.35)  # the stems lie under murky liquor
    for _ in range(10):  # scum and bubbles on the surface
        x, y = rnd.uniform(surf[3][0] + 20, surf[2][0] - 30), rnd.uniform(y_top + 8, y_bot - 6)
        ic.shade(ic.intersect(sm, ic.mask("ellipse", (x - 30, y - 7, x + 30, y + 7))), (196, 186, 104), 0.3, blur=5)
    ic.line([(70, y_top + 56), (440, y_top + 40)], 26, (70, 50, 32))
    ic.line([(70, y_top + 50), (440, y_top + 34)], 8, (150, 116, 80))
    for bx in (150, 330):  # stones weighting the beam
        ic.rock([(bx - 26, y_top + 40), (bx - 18, y_top + 20), (bx + 12, y_top + 16), (bx + 28, y_top + 32), (bx + 20, y_top + 48),
                 (bx - 16, y_top + 50)])

    # beating vat (lower): deep indigo, darker towards its walls, dasher paddles plunged in the liquor
    sm2, surf2 = vat(ic, 360, 950, 910, 992, 180, INDIGO, rim_w=24)
    core = ic.mask("ellipse", (surf2[3][0] + 30, surf2[3][1] + 10, surf2[2][0] - 30, surf2[0][1] - 6)).filter(ImageFilter.GaussianBlur(40))
    ic.shade(ic.intersect(sm2, ImageChops.invert(core)), (4, 8, 34), 0.55)
    paddles = (((560, 842), (520, 650)), ((782, 848), (818, 656)))
    for (bx, by), (tx, ty) in paddles:
        # the blade under the surface, dimmed by the liquor
        blade = ic.poly_mask([(bx - 30, by + 2), (bx + 30, by + 2), (bx + 26, by + 34), (bx - 26, by + 34)])
        ic.fill(ic.intersect(blade, sm2), "#4a3c40", "#1a1830", (by, by + 34), noise=0.1)
        ic.shade(ic.intersect(blade, sm2), (20, 36, 96), 0.5)
    froth(ic, sm2, [p[0] for p in paddles] + [(670, 866)], 26, 36)
    for (bx, by), (tx, ty) in paddles:
        ic.line([(bx, by), (tx, ty)], 18, (58, 40, 24))
        ic.line([(bx - 3, by), (tx - 3, ty)], 8, (150, 112, 74))
        ic.line([(tx - 24, ty + 2), (tx + 24, ty - 2)], 14, (58, 40, 24))  # T grip of the dasher
        ic.line([(tx - 22, ty - 1), (tx + 22, ty - 5)], 5, (160, 122, 80))
        ic.overlay(lambda d, bx=bx, by=by: d.ellipse((bx - 22, by - 6, bx + 22, by + 8), outline=(226, 236, 248, 200), width=4))
    # a sluice spout from the upper vat into the lower
    ic.poly([(400, 786), (440, 786), (452, 812), (410, 816)], "#8a6a48", "#4a3420", edge=3)
    ic.line([(430, 814), (436, 842)], 12, (130, 132, 60, 220))

    # basket of cut indigo, front left
    ic.shade(ic.mask("ellipse", (0, 960, 220, 1004)), alpha=0.45, blur=8)
    for k in range(6):
        cut_plant(ic, 60 + k * 18, 900, rnd.uniform(70, 90), -120 + k * 12)
    ic.basket(20, 900, 200, 996)
