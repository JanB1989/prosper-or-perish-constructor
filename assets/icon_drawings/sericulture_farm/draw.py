"""Silk Farm (sericulture): a mulberry tree beside a small rearing house with shelves of silkworm
trays, a flat basket heaped with cocoons.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/sericulture_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/sericulture_farm

Identity: a round flat basket heaped with cream and golden cocoons at the bottom right; a broad
mulberry tree with dark berries on the left; between them a modest lime-washed rearing house under a
clay-tile roof whose open front shows tiers of trays of leaves and pale silkworms. Tier 0 of the
sericulture chain (the Regulated Sericulture Farm adds the long rearing house and reeling basins).

Local helpers are shared by the fibre and silk family (cotton, fibre dressing, sericulture).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
REFS = ("fruit_orchard", "farming_village", "llotja_seda", "lucca_silk_production_guild")

CREAM = ((226, 218, 190), (250, 246, 230), (150, 138, 108))
IVORY = ((238, 232, 212), (255, 252, 242), (160, 150, 124))
GOLD = ((214, 166, 72), (242, 208, 126), (126, 90, 32))


# ---------------------------------------------------------------- helpers (shared by the fibre and silk family)
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def scale(c, f: float) -> tuple:
    return tuple(int(max(0, min(255, v * f))) for v in rgb(c))


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def timber(ic: Icon, p0, p1, width: float, c1="#8a6440", c2="#4e3522") -> None:
    """Squared beam: lit upper half, darker lower half, a grain highlight, soft rim."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    if abs(x1 - x0) < abs(y1 - y0):  # upright: the right half is in shade
        lower = [(x0, y0), (x1, y1)] + ([pts[2], pts[3]] if nx > 0 else [pts[1], pts[0]])
    else:
        lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def planks(ic: Icon, pts, c1="#8e6a46", c2="#4e3522", board: float = 30) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(30 * t)) if t > 0 else (20, 12, 6, int(-44 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping shingles: per-tile tone, lit lower lip, soft course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow = Image.new("L", (SIZE, SIZE), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys), 0
    while y < max(ys):
        off = (k % 2) * stagger / 2 + rnd(-6, 6)
        x = min(xs) - stagger + off
        while x < max(xs):
            w = stagger * rnd(0.85, 1.15)
            q = [(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + course), (x + 2, y + course)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(20, 10, 6, int(-t * 60)) if t < 0 else (255, 236, 210, int(t * 40)))
            td.line([(x + w - 2, y + 6), (x + w - 2, y + course - 2)], fill=(40, 22, 14, 90), width=3)
            x += w
        yl = y + course + rnd(-2, 2)
        td.line([(0, yl - 4), (SIZE, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (SIZE, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    if edge:
        ic.outline(pts, edge)
    return m


def pantiles(ic: Icon, ridge, eave, c1="#b8683e", c2="#6c3620", step: float = 30, edge: int = 6) -> Image.Image:
    """Roof of curved clay tiles in columns from ridge to eave: each column a rounded barrel (lit left,
    dark right), faint courses, a dark eave shadow. ``ridge`` and ``eave`` are (left, right) points."""
    (rl, rr), (el, er) = ridge, eave
    pts = [rl, rr, er, el]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(rl[1], rr[1]), max(el[1], er[1])), noise=0.2, chroma=0.1)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    n = max(2, int((er[0] - el[0]) / step))
    for i in range(n + 1):
        t = i / n
        top = (rl[0] + (rr[0] - rl[0]) * t, rl[1] + (rr[1] - rl[1]) * t)
        bot = (el[0] + (er[0] - el[0]) * t, el[1] + (er[1] - el[1]) * t)
        w = (er[0] - el[0]) / n
        tone = rnd(-1, 1)
        col = (255, 228, 200, int(24 * tone)) if tone > 0 else (30, 10, 4, int(-40 * tone))
        d.polygon([top, (top[0] + w * 0.8, top[1]), (bot[0] + w, bot[1]), bot], fill=col)
        d.line([(top[0] + w * 0.25, top[1]), (bot[0] + w * 0.3, bot[1])], fill=(255, 226, 190, 80), width=max(3, int(w * 0.18)))
        d.line([(top[0] + w * 0.8, top[1]), (bot[0] + w * 0.95, bot[1])], fill=(40, 14, 6, 150), width=max(3, int(w * 0.2)))
    for f in np.arange(0.12, 1.0, 0.13):
        y0 = rl[1] + (el[1] - rl[1]) * f
        d.line([(0, y0 + rnd(-2, 2)), (SIZE, y0 + rnd(-2, 2))], fill=(40, 14, 6, 60), width=3)
    paste_clipped(ic, lay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, min(el[1], er[1]) - 26, SIZE, SIZE))), (30, 10, 4), 0.35, blur=6)
    if edge:
        ic.outline(pts, edge)
    return m


def plaster(ic: Icon, box, c1="#dcccaa", c2="#b09a74", grime: float = 0.35) -> Image.Image:
    """Lime-washed wall: warm gradient, blotches of worn wash, grime rising from the foot."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.22, chroma=0.12)
    rnd = ic.random
    for _ in range(int((x1 - x0) * (y1 - y0) / 9000) + 3):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(14, 40)
        light = rnd.random() < 0.45
        tint(ic, ic.mask("ellipse", (x - r * 1.3, y - r, x + r * 1.3, y + r)), m,
             (255, 246, 226) if light else (70, 52, 34), 0.12 if light else 0.14, 8)
    tint(ic, ic.mask("rectangle", (x0, y1 - (y1 - y0) * 0.22, x1, y1 + 30)), m, (60, 50, 34), grime, 18)
    return m


def thatch(ic: Icon, ridge, eave, c=("#b8a06a", "#6c5632")) -> Image.Image:
    """Thatched roof plane: overlapping courses of straw with ragged edges, a cut eave. Returns the mask."""
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
        tn = rnd.uniform(0.92, 1.06)
        ic.fill(band, scale(c[0], tn), scale(c[1], tn), (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(240):
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
    ic.line([tuple(p) for p in ridge], 22, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 8, (150, 128, 84, 170))
    return union(m, ic.poly_mask(lip))


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float, light="#6a8e3c", dark="#1a2e12",
           blobs: int = 22, dab: tuple = (4, 9)) -> Image.Image:
    """Tree crown: irregular blobs lit from the upper left, leaf dabs, shaded underside. Returns the mask."""
    rnd = ic.random
    m = blank()
    bl = []
    for _ in range(blobs):
        u = rnd.uniform(-0.8, 0.8)
        bl.append((cx + u * rx, cy - ry * 0.32 * (1 - u * u) + rnd.uniform(-ry * 0.28, ry * 0.32),
                   ry * rnd.uniform(0.3, 0.48) * (1.1 - 0.3 * abs(u))))
    for _ in range(int(blobs * 1.1)):
        u = rnd.uniform(-0.88, 0.88)
        bl.append((cx + u * rx, cy - ry * 0.75 * math.sqrt(1 - u * u) + rnd.uniform(0, ry * 0.25),
                   ry * rnd.uniform(0.14, 0.24)))
    bl.sort(key=lambda b: b[1])
    for bx, by, br in bl:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.3, br, 28, 0.07))
        ic.fill(bm, light, dark, radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.28, chroma=0.14)
        m = union(m, bm)
    x0, x1, y0, y1 = cx - rx * 1.05, cx + rx * 1.05, cy - ry * 1.2, cy + ry
    lc = tuple(min(255, int(v * 1.5)) for v in rgb(light))

    def dabs(dr):
        for _ in range(int(rx * ry / 45)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            v = (y - cy) / ry
            r = rnd.uniform(*dab)
            col = lc + (70,) if rnd.random() < 0.5 - 0.5 * v else (22, 34, 12, 70)
            dr.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + ry * 0.05, SIZE, SIZE))), (14, 22, 8), 0.40, blur=22)
    return m


def basket(ic: Icon, x0, y0, x1, y1, colors=("#b58d55", "#5e4226")) -> Image.Image:
    """Tapered wicker basket, rim ellipse at y0; woven courses shaded as a cylinder. Returns the body mask."""
    w = x1 - x0
    cx = (x0 + x1) / 2
    lip = w * 0.13
    ts = np.linspace(0, 1, 20)
    left = [(x0 + w * 0.1 * t, y0 + (y1 - y0) * t) for t in ts]
    bottom = [(cx + math.cos(a) * (w / 2 - w * 0.1), y1 + math.sin(a) * lip * 0.8) for a in np.linspace(0, math.pi, 16)]
    right = [(x1 - w * 0.1 * t, y0 + (y1 - y0) * t) for t in ts[::-1]]
    top = [(cx + math.cos(a) * w / 2, y0 + math.sin(a) * lip) for a in np.linspace(math.pi, 0, 16)]
    pts = left + bottom[::-1] + right + [(x0, y0)]
    body = union(ic.poly_mask(pts), ic.mask("ellipse", (x0, y0 - lip, x1, y0 + lip)))
    ic.fill(body, colors[0], colors[1], radial=(x0 + w * 0.25, y0, w * 1.1), noise=0.24)

    def weave(d):
        for y in np.arange(y0 + 12, y1 + lip, 15):
            d.arc((x0 - 4, y - lip, x1 + 4, y + lip), 0, 180, fill=(60, 40, 20, 150), width=4)
            d.arc((x0 - 4, y - lip - 6, x1 + 4, y + lip - 6), 20, 160, fill=(240, 214, 160, 60), width=3)
        for x in np.arange(x0 + 12, x1, 20):
            d.line([(x, y0), (x + (cx - x) * 0.12, y1 + lip * 0.6)], fill=(50, 32, 16, 90), width=3)

    ic.overlay(weave, body)
    tint(ic, ic.mask("rectangle", (cx + w * 0.12, y0 - 20, x1 + 20, y1 + 30)), body, (16, 10, 4), 0.35, 14)
    rim_m = ic.mask("ellipse", (x0, y0 - lip, x1, y0 + lip))
    ic.fill(rim_m, "#3a2a18", "#20160c", (y0 - lip, y0 + lip))
    ic.overlay(lambda d: d.ellipse((x0, y0 - lip, x1, y0 + lip), outline=(170, 130, 80, 255), width=9))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return body


def lint_heap(ic: Icon, cx, cy, rx, ry, clip: Image.Image | None = None, n: int = 60) -> None:
    """Heap of loose white cotton: many soft puffs, lit from the upper left, grey-blue in shadow."""
    rnd = ic.random
    items = []
    for _ in range(n):
        a = rnd.uniform(math.pi, 2 * math.pi)
        r = rnd.random() ** 0.7
        x = cx + math.cos(a) * rx * r
        y = cy + math.sin(a) * ry * r + rnd.uniform(0, ry * 0.35)
        items.append((x, y, rnd.uniform(0.18, 0.28) * min(rx, ry * 2)))
    items.sort(key=lambda it: it[1])
    body = ic.poly_mask(ic.jitter(cx, cy - ry * 0.35, rx * 0.95, ry * 0.7, 16, 0.08)
                        ) if n > 20 else None
    if body is not None:
        body = ic.intersect(body, clip) if clip is not None else body
        ic.fill(body, "#ecebe4", "#8e8e92", radial=(cx - rx * 0.6, cy - ry, max(rx, ry) * 2.0), noise=0.14)

    def paint(d):
        for x, y, r in items:
            d.ellipse((x - r * 1.1 + r * 0.25, y - r * 0.8 + r * 0.3, x + r * 1.1 + r * 0.25, y + r * 0.8 + r * 0.3),
                      fill=(146, 144, 140, 255))
            d.ellipse((x - r * 1.1, y - r * 0.8, x + r * 1.1, y + r * 0.8), fill=(224, 220, 208, 255))
            d.ellipse((x - r * 0.8, y - r * 0.7, x + r * 0.35, y + r * 0.1), fill=(248, 246, 238, 220))

    ic.overlay(paint, clip)
    shadow = ic.mask("ellipse", (cx - rx * 0.1, cy - ry * 0.9, cx + rx * 1.3, cy + ry * 0.6))
    if clip is not None:
        shadow = ic.intersect(shadow, clip)
    ic.shade(shadow, (40, 44, 62), 0.34, blur=20)


def bolls(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Open cotton bolls (x, y, r): a dark brown star of bracts behind three or four fluffy lobes,
    each lobe with a grey shadow side, a warm white body and a bright lit top."""
    rnd = ic.random

    def paint(d):
        for x, y, r in items:
            a0 = rnd.uniform(0, math.pi)
            for k in range(5):
                a = a0 + k * 2 * math.pi / 5
                tip = (x + math.cos(a) * r * 1.25, y + math.sin(a) * r * 1.1)
                s1 = (x + math.cos(a + 0.5) * r * 0.5, y + math.sin(a + 0.5) * r * 0.5)
                s2 = (x + math.cos(a - 0.5) * r * 0.5, y + math.sin(a - 0.5) * r * 0.5)
                d.polygon([s1, tip, s2], fill=(78, 50, 30, 255))
            lobes = [(-0.42, 0.08), (0.42, 0.1), (0.02, -0.34), (0.0, 0.36)][: rnd.choice((3, 4, 4))]
            lobes.sort(key=lambda p: p[1])
            for dx, dy in lobes:
                lr = r * rnd.uniform(0.56, 0.66)
                px, py = x + dx * r, y + dy * r
                d.ellipse((px - lr + lr * 0.16, py - lr * 0.9 + lr * 0.2, px + lr + lr * 0.16, py + lr * 0.9 + lr * 0.2),
                          fill=(128, 124, 120, 255))
                d.ellipse((px - lr, py - lr * 0.9, px + lr, py + lr * 0.9), fill=(222, 218, 204, 255))
                d.ellipse((px - lr * 0.75, py - lr * 0.8, px + lr * 0.3, py + lr * 0.1), fill=(250, 248, 240, 230))

    ic.overlay(paint, clip)


def cotton_bush(ic: Icon, cx: float, base: float, h: float, w: float, density: float = 1.0,
                boll_r: float = 20) -> Image.Image:
    """Cotton plant at picking time: woody red-brown stems, a loose mass of dark palmate leaves (some
    turning bronze), open white bolls all over its upper half. Returns the plant mask."""
    rnd = ic.random
    acc = [blank()]
    for _ in range(6):
        tx, ty = cx + rnd.uniform(-w * 0.3, w * 0.3), base - h * rnd.uniform(0.4, 0.7)
        ic.line([(cx + rnd.uniform(-8, 8), base), ((cx + tx) / 2, (base + ty) / 2 + 10), (tx, ty)], 9, (70, 44, 30))
    blobs = []
    for _ in range(16):
        u = rnd.uniform(-1, 1)
        bx = cx + u * w * 0.36
        by = base - h * (0.3 + 0.44 * rnd.random()) * (1 - 0.3 * abs(u))
        br = w * rnd.uniform(0.16, 0.25)
        blobs.append((by, bx, br))
    blobs.sort()
    for by, bx, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.25, br, 14, 0.22))
        if rnd.random() < 0.22:
            c1, c2 = "#7c6a36", "#2c2210"
        else:
            c1, c2 = "#5f7a36", "#16220a"
        ic.fill(bm, c1, c2, radial=(bx - br * 0.7, by - br * 0.8, br * 2.3), noise=0.3, chroma=0.14)
        acc[0] = union(acc[0], bm)
    m = acc[0]

    def leaves(d):  # palmate leaf dabs: three small lobes each
        for _ in range(int(w * h / 1600)):
            x, y = cx + rnd.uniform(-w * 0.5, w * 0.5), base - h * rnd.uniform(0.2, 0.8)
            s = rnd.uniform(9, 15)
            lit = rnd.random() < 0.5
            col = (126, 150, 72, 110) if lit else (18, 30, 8, 110)
            for a in (-0.9, 0, 0.9):
                ax, ay = x + math.sin(a) * s, y - math.cos(a) * s
                d.ellipse((ax - s * 0.55, ay - s * 0.55, ax + s * 0.55, ay + s * 0.55), fill=col)

    ic.overlay(leaves, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, base - h * 0.35, SIZE, SIZE))), (8, 14, 4), 0.35, blur=18)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - w * 0.05, base - h * 0.75, cx + w * 0.9, base + h * 0.3))), (8, 14, 4),
             0.3, blur=24)
    items = []
    for _ in range(int(9 * density * w / 160)):
        u = rnd.uniform(-1, 1)
        x = cx + u * w * 0.4
        y = base - h * (0.35 + 0.55 * rnd.random()) * (1 - 0.35 * u * u)
        items.append((x, y, boll_r * rnd.uniform(0.8, 1.15)))
    items.sort(key=lambda it: it[1])
    bolls(ic, items)
    return m


def bale(ic: Icon, x0, y0, x1, y1, depth: float = 34, cloth=("#b8a07a", "#62503a"), bands: int = 4) -> Image.Image:
    """Pressed cotton bale in coarse bagging: lit top face, a front that bulges between tight rope
    bands, lint squeezed out at the seams."""
    rnd = ic.random
    w, h = x1 - x0, y1 - y0
    top = [(x0 + 14, y0 - depth), (x1 - 8, y0 - depth), (x1 - 2, y0 + 4), (x0 + 2, y0 + 4)]
    tm = ic.poly_mask(top)
    ic.fill(tm, scale(cloth[0], 1.18), scale(cloth[0], 1.02), (y0 - depth, y0), noise=0.22)
    front = ic.mask("rounded_rectangle", (x0, y0, x1, y1), radius=12)
    ic.fill(front, cloth[0], cloth[1], radial=(x0 + w * 0.25, y0 + h * 0.2, max(w, h) * 1.15), noise=0.26, chroma=0.1)
    tint(ic, ic.mask("rectangle", (x0 - 10, y1 - h * 0.25, x1 + 10, y1 + 20)), front, (20, 12, 6), 0.3, 12)
    tint(ic, ic.mask("rectangle", (x1 - w * 0.25, y0 - 10, x1 + 20, y1 + 10)), front, (20, 12, 6), 0.3, 14)
    both = union(front, tm)

    def texture(d):
        for y in np.arange(y0 - depth + 6, y1, 13):
            d.line([(x0, y), (x1, y + rnd.uniform(-3, 3))], fill=(50, 36, 20, 28), width=2)
        for _ in range(int(w * h / 900)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0 - depth, y1)
            d.line([(x, y), (x + rnd.uniform(-6, 6), y + rnd.uniform(6, 14))], fill=(255, 236, 196, 40), width=2)

    ic.overlay(texture, both)
    xs = [x0 + w * (i + 0.5) / bands + rnd.uniform(-6, 6) for i in range(bands)]
    for xa, xb in zip([x0] + xs, xs + [x1]):  # bagging bulges between the bands
        tint(ic, ic.mask("ellipse", (xa + 8, y0 + h * 0.12, xb - 8, y1 - h * 0.3)), front, (255, 244, 220), 0.16, 10)
    for bx in xs:
        k = (bx - (x0 + x1) / 2) / w
        path = [(bx + k * 16, y0 - depth), (bx, y0 + 2), (bx - 3, (y0 + y1) / 2), (bx, y1 - 2)]
        ic.shade(ic.intersect(both, ic.poly_mask([(bx - 22, y0 - depth), (bx + 22, y0 - depth), (bx + 22, y1),
                                                   (bx - 22, y1)])), (20, 12, 6), 0.22, blur=8)
        ic.line(path, 12, (44, 30, 16))
        ic.line([(px - 3, py) for px, py in path], 4, (160, 124, 80, 170))
    items = [(x0 + rnd.uniform(10, w - 10), y0 + rnd.uniform(-4, 6), rnd.uniform(7, 12)) for _ in range(4)]
    items += [(x0 + rnd.uniform(-2, 4), y0 + rnd.uniform(10, h - 10), rnd.uniform(6, 10)) for _ in range(2)]

    def tufts(d):
        for x, y, r in items:
            d.ellipse((x - r + 2, y - r * 0.7 + 3, x + r + 2, y + r * 0.7 + 3), fill=(140, 136, 128, 200))
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(236, 232, 222, 240))

    ic.overlay(tufts, both)
    ic.outline(top, 4, (40, 26, 16, 170))
    ic.overlay(lambda d: d.rounded_rectangle((x0, y0, x1, y1), radius=12, outline=(40, 26, 16, 170), width=4))
    return both


def wheel(ic: Icon, cx, cy, r, spokes: int = 8, rim: float = 18, wood=((150, 108, 66), (74, 50, 30))) -> None:
    """Spoked wooden wheel seen face-on: shaded rim, turned spokes, hub; light from the upper left."""
    outer = ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    inner = ic.mask("ellipse", (cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim))
    ring = ImageChops.subtract(outer, inner)
    for k in range(spokes):
        a = k * 2 * math.pi / spokes + 0.2
        p1 = (cx + math.cos(a) * (r - rim * 0.6), cy + math.sin(a) * (r - rim * 0.6))
        ic.line([(cx, cy), p1], 13, (44, 30, 18))
        ic.line([(cx, cy), p1], 8, wood[0])
    ic.fill(ring, wood[0], wood[1], radial=(cx - r * 0.7, cy - r * 0.7, r * 2.2), noise=0.18)
    ic.overlay(lambda d: d.arc((cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5), 160, 290, fill=(240, 210, 160, 110), width=4))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 26, 16, 200), width=5))
    ic.overlay(lambda d: d.ellipse((cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim), outline=(40, 26, 16, 160), width=4))
    hr = rim * 1.2
    ic.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), wood[0], wood[1], edge=4)


def hank(ic: Icon, x: float, top: float, length: float, width: float, colors=("#e6d6a8", "#a08a58"),
         sway: float = 0.0) -> Image.Image:
    """Strick of dressed fibre hanging over a rail: narrow fold at the top, flaring into long straight
    strands with a lit left side, a shaded right side and a ragged tip."""
    rnd = ic.random
    ts = np.linspace(0, 1, 24)
    prof = [width / 2 * (0.55 + 0.45 * min(1, t / 0.12)) * (1 - 0.18 * t) for t in ts]
    spine = [(x + sway * length * t * t, top + length * t) for t in ts]
    left = [(sx - p, sy) for (sx, sy), p in zip(spine, prof)]
    right = [(sx + p, sy) for (sx, sy), p in zip(spine, prof)]
    tip = [(spine[-1][0] + dx, spine[-1][1] + rnd.uniform(-14, 22)) for dx in np.linspace(prof[-1], -prof[-1], 9)]
    pts = left + tip + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], (top, top + length), noise=0.18, chroma=0.08)
    ic.shade(ic.intersect(m, ic.poly_mask(spine + right[::-1])), (40, 28, 10), 0.28)

    def strands(d):
        for _ in range(int(width / 3)):
            f = rnd.uniform(-0.9, 0.9)
            pl = [(sx + f * p, sy) for (sx, sy), p in zip(spine, prof)]
            col = (255, 246, 214, 90) if f < 0.1 and rnd.random() < 0.6 else (70, 52, 24, 80)
            d.line(pl, fill=col, width=2)

    ic.overlay(strands, m)

    def twist(d):  # the strick is twisted at its head
        for k in range(4):
            y = top + 10 + k * width * 0.4
            d.line([(x - width * 0.5, y), (x + width * 0.5, y + width * 0.3)], fill=(60, 44, 18, 110), width=4)
            d.line([(x - width * 0.5, y - 5), (x + width * 0.5, y + width * 0.3 - 5)], fill=(255, 244, 210, 70), width=3)

    ic.overlay(twist, m)
    ic.outline(pts, 3, (50, 36, 18, 150))
    return m


def cocoons(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Silk cocoons (x, y, r, angle, palette): peanut-waisted ovals with a shadow side, a lit
    top and a faint silky sheen. Palette = (mid, lit, dark)."""

    def paint(d):
        for x, y, r, ang, (mid, lit, dk) in items:
            c, s = math.cos(ang), math.sin(ang)

            def oval(ox, oy, rx, ry, n=20):
                pts = []
                for k in range(n):
                    a = 2 * math.pi * k / n
                    wx = math.cos(a) * rx
                    wy = math.sin(a) * ry * (1 - 0.12 * math.cos(2 * a) ** 2)
                    pts.append((ox + wx * c - wy * s, oy + wx * s + wy * c))
                return pts

            d.polygon(oval(x + r * 0.12, y + r * 0.16, r, r * 0.62), fill=dk + (255,))
            d.polygon(oval(x, y, r * 0.96, r * 0.58), fill=mid + (255,))
            d.polygon(oval(x - r * 0.22, y - r * 0.2, r * 0.58, r * 0.28), fill=lit + (220,))

    ic.overlay(paint, clip)


def worms(ic: Icon, clip: Image.Image, box, n: int) -> None:
    """Pale silkworms (short curved grubs) scattered over mulberry leaves in a tray."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            a = rnd.uniform(0, math.pi)
            L = rnd.uniform(18, 26)
            pts = [(x + math.cos(a) * L * t + math.sin(a) * 4 * math.sin(math.pi * t),
                    y + math.sin(a) * L * t * 0.6) for t in np.linspace(-0.5, 0.5, 6)]
            d.line([(px + 2, py + 3) for px, py in pts], fill=(70, 70, 50, 170), width=9, joint="curve")
            d.line(pts, fill=(226, 222, 200, 255), width=8, joint="curve")
            d.line([(px - 1, py - 2) for px, py in pts[1:-1]], fill=(252, 250, 240, 200), width=3)

    ic.overlay(paint, clip)


def leaf_bed(ic: Icon, clip: Image.Image, box, n: int = 90) -> None:
    """Chopped mulberry leaves spread over a tray: overlapping broad green dabs, lit and shadowed."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.fill(clip, "#4e6e2c", "#26380f", (y0, y1), noise=0.3)

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            r = rnd.uniform(10, 18)
            t = rnd.random()
            col = (120, 150, 64, 200) if t < 0.4 else (70, 98, 38, 200) if t < 0.8 else (30, 46, 14, 200)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=col)

    ic.overlay(paint, clip)


def steam(ic: Icon, x: float, y: float, h: float, w: float = 40) -> None:
    """Soft rising steam, kept inside painted pixels so it never grows the silhouette."""
    rnd = ic.random
    for k in range(6):
        t = k / 5
        cx = x + math.sin(t * 3.0) * w * 0.5
        cy = y - h * t
        r = w * (0.5 + 0.7 * t)
        ic.shade(ic.mask("ellipse", (cx - r, cy - r * 0.7, cx + r, cy + r * 0.7)), (236, 234, 226), 0.32 * (1 - t * 0.6),
                 blur=12)


def ground_strip(ic: Icon, x0, x1, y0, y1, c=("#735a3a", "#4a3a26"), clods: int = 30) -> None:
    """Strip of trodden earth with a ragged back edge, clods and pebbles."""
    rnd = ic.random
    top = [(x0, y0 + 16)] + [(x, y0 + rnd.uniform(-10, 10)) for x in np.linspace(x0 + 40, x1 - 40, 12)] + [(x1, y0 + 14)]
    pts = top + [(x1 + 4, y1 - 10), ((x0 + x1) / 2, y1), (x0 - 2, y1 - 8)]
    ic.poly(pts, c[0], c[1], noise=0.32, edge=3)
    for _ in range(clods):
        x, y = rnd.uniform(x0 + 20, x1 - 20), rnd.uniform(y0 + 10, y1 - 10)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)


def sheaf(ic: Icon, foot, head, width: float, colors=("#c8aa62", "#6a5226"), seeds: bool = True) -> Image.Image:
    """One bundle of flax or hemp stalks from ``foot`` to ``head``: long straight stems, lit left edge,
    a twine tie, a brush of seed bolls at the head. Returns the mask."""
    rnd = ic.random
    (fx, fy), (hx, hy) = foot, head
    L = math.hypot(hx - fx, hy - fy)
    ux, uy = (hx - fx) / L, (hy - fy) / L
    nx, ny = -uy, ux
    hw = width / 2

    def at(t, f):
        w = hw * (1.0 - 0.35 * math.sin(math.pi * min(t / 0.8, 1)) * 0.6)
        return (fx + ux * L * t + nx * w * f, fy + uy * L * t + ny * w * f)

    ts = np.linspace(0, 0.86, 14)
    pts = [at(t, -1) for t in ts] + [at(t, 1) for t in ts[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], (min(fy, hy), max(fy, hy)), noise=0.22, chroma=0.1)
    ic.shade(ic.intersect(m, ic.poly_mask([at(t, 0) for t in ts] + [at(t, 1) for t in ts[::-1]])), (30, 20, 6), 0.3)

    def stems(d):
        for _ in range(int(width / 3)):
            f = rnd.uniform(-0.95, 0.95)
            col = (250, 230, 160, 90) if f < 0 and rnd.random() < 0.6 else (60, 42, 14, 90)
            d.line([at(0, f), at(0.86, f * 0.9)], fill=col, width=2)

    ic.overlay(stems, m)
    ic.outline(pts, 3, (50, 34, 12, 150))
    tie = at(0.62, 0)
    ic.line([at(0.62, -1.05), at(0.62, 1.05)], 8, (82, 60, 30))
    if seeds:
        heads = []
        for _ in range(int(width / 4)):
            f = rnd.uniform(-1.2, 1.2)
            p0 = at(0.84, f * 0.8)
            q = (p0[0] + ux * L * rnd.uniform(0.06, 0.16) + nx * f * 10, p0[1] + uy * L * rnd.uniform(0.06, 0.16) + ny * f * 10)
            heads.append((p0, q))

        def brush(d):
            for p0, q in heads:
                d.line([p0, q], fill=(96, 78, 38, 255), width=4)
                r = rnd.uniform(4, 7)
                c = (150, 120, 60, 255) if rnd.random() < 0.6 else (104, 82, 40, 255)
                d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=c)
                d.ellipse((q[0] - r * 0.7, q[1] - r * 0.7, q[0], q[1]), fill=(200, 170, 100, 200))

        ic.overlay(brush)
    return m


def stook(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Stook of flax sheaves leaning together to dry: back sheaves darker, front ones lit."""
    rnd = ic.random
    n = 8
    order = sorted(range(n), key=lambda i: -abs(i - (n - 1) / 2) + rnd.uniform(-0.3, 0.3))
    for k, i in enumerate(order):
        f = (i - (n - 1) / 2) / ((n - 1) / 2)
        tone = 0.72 + 0.3 * k / (n - 1)
        foot = (cx + f * w * 0.5, base + rnd.uniform(-6, 6) - (1 - abs(f)) * 10)
        head = (cx + f * w * 0.1 + rnd.uniform(-6, 6), base - h + abs(f) * 30)
        sheaf(ic, foot, head, w * 0.2, (scale("#c09a4e", tone), scale("#5e4420", tone)))
    ic.line([(cx - w * 0.2, base - h * 0.52), (cx + w * 0.2, base - h * 0.5)], 9, (82, 60, 30))


def mleaf(ic: Icon, base, deg: float, length: float, colors=("#78a040", "#1e3410")) -> None:
    """Broad heart-shaped mulberry leaf with a toothed edge, lit and shadow halves, pale midrib."""
    rnd = ic.random
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 22)
    hw = [length * 0.42 * (math.sin(math.pi * min(1, t * 1.1)) ** 0.7) * (1 - 0.35 * t) + (length * 0.08 if t < 0.1 else 0)
          for t in ts]
    spine = [b + d * length * t for t in ts]
    s1 = [p + n * w * (1 + 0.06 * (k % 2)) for k, (p, w) in enumerate(zip(spine, hw))]
    s2 = [p - n * w * (1 + 0.06 * (k % 2)) for k, (p, w) in enumerate(zip(spine, hw))]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1], radial=(min(xs), min(ys), length * 1.2), noise=0.2, chroma=0.12)
    lower = s1 if n[1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (8, 16, 4), 0.28)
    ic.line([tuple(p) for p in spine[1:-3]], 3, (170, 196, 120, 110))
    ic.outline(pts, 3, (16, 28, 8, 130))


def tray_rack(ic: Icon, x0, x1, tops, depth: float = 26) -> None:
    """Shelves of shallow rearing trays: a thin wooden front lip, green leaf bed with worms on top."""
    for y in tops:
        top = ic.poly_mask([(x0 + 8, y - depth), (x1 - 8, y - depth), (x1, y), (x0, y)])
        leaf_bed(ic, top, (x0, y - depth, x1, y), n=int((x1 - x0) / 5))
        worms(ic, top, (x0 + 10, y - depth + 4, x1 - 10, y - 4), int((x1 - x0) / 18))
        ic.rect((x0 - 4, y, x1 + 4, y + 16), "#b08658", "#6a4a2c", edge=4)


def peanut(ic: Icon, x, y, r, ang, pal, halo: bool = True) -> None:
    """One large silk cocoon: an elongated peanut with a slight waist, form-shaded (warm lit side,
    grey-ochre shadow side), a lit top and a faint fuzzy floss halo. ``pal`` = (mid, lit, dark)."""
    mid, lit, dk = pal
    c, s = math.cos(ang), math.sin(ang)

    def shape(ox, oy, k=1.0, n=36):
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            wx = math.cos(a) * r * k
            wy = math.sin(a) * r * 0.58 * k * (1 - 0.24 * math.exp(-(math.cos(a) * 3.0) ** 2))  # slight waist
            pts.append((ox + wx * c - wy * s, oy + wx * s + wy * c))
        return pts

    if halo:
        ic.shade(ic.poly_mask(shape(x, y, 1.14)), lit, 0.3, blur=4)
    ic.shade(ic.poly_mask(shape(x + r * 0.14, y + r * 0.2)), (40, 30, 16), 0.55, blur=4)
    m = ic.poly_mask(shape(x, y))
    ic.fill(m, lit, dk, radial=(x - r * 0.45, y - r * 0.4, r * 1.7), noise=0.12, chroma=0.05)
    ic.shade(ic.intersect(m, ic.poly_mask(shape(x - r * 0.25, y - r * 0.22, 0.55))), (255, 252, 240), 0.35, blur=4)

    def fuzz(d):
        rnd = ic.random
        for _ in range(5):
            a = rnd.uniform(math.pi * 0.9, math.pi * 1.8)
            px, py = x + math.cos(a) * r * 0.9, y + math.sin(a) * r * 0.5
            d.line([(px, py), (px + math.cos(a) * 5, py + math.sin(a) * 4)], fill=tuple(lit) + (80,), width=2)

    ic.overlay(fuzz)
    ic.outline(shape(x, y), 2, (90, 70, 40, 110))


def sieve(ic: Icon, x0, y0, x1, y1, depth: float) -> tuple:
    """Deep round bamboo sieve seen from slightly above: woven body, inner shadow, thick lit rim.
    Returns (inner mask, front-rim painter) so contents can be drawn between the two."""
    cx, w = (x0 + x1) / 2, x1 - x0
    rim_h = (y1 - y0)
    body = union(ic.mask("ellipse", (x0, y0, x1, y1)),
                 ic.poly_mask([(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), (x1 - w * 0.08, (y0 + y1) / 2 + depth),
                               (x0 + w * 0.08, (y0 + y1) / 2 + depth)]),
                 ic.mask("ellipse", (x0 + w * 0.08, (y0 + y1) / 2 + depth - rim_h * 0.4, x1 - w * 0.08,
                                     (y0 + y1) / 2 + depth + rim_h * 0.4)))
    ic.fill(body, "#c09a5c", "#5a3e1e", radial=(x0 + w * 0.2, y0, w * 1.0), noise=0.26, chroma=0.1)

    def weave(d):
        for k in range(12):
            yy = (y0 + y1) / 2 + depth * k / 11
            d.arc((x0 + w * 0.08 * k / 11, yy - rim_h * 0.42, x1 - w * 0.08 * k / 11, yy + rim_h * 0.42), 0, 180,
                  fill=(70, 46, 20, 130) if k % 2 else (230, 200, 140, 70), width=3)
        for x in np.arange(x0 + 10, x1, 16):
            d.line([(x, (y0 + y1) / 2), (x + (cx - x) * 0.08, (y0 + y1) / 2 + depth + rim_h * 0.3)], fill=(60, 40, 18, 70), width=3)

    ic.overlay(weave, body)
    tint(ic, ic.mask("rectangle", (cx + w * 0.15, y0, x1 + 20, y1 + depth + 40)), body, (20, 12, 4), 0.35, 20)
    inner = ic.mask("ellipse", (x0 + 12, y0 + 8, x1 - 12, y1 - 8))
    ic.fill(inner, "#3a2814", "#6a4a26", (y0, y1), noise=0.2)
    tint(ic, ic.mask("ellipse", (x0, y0 - 20, x1, (y0 + y1) / 2 + 6)), inner, (10, 6, 2), 0.5, 10)
    ic.overlay(lambda d: d.ellipse((x0, y0, x1, y1), outline=(90, 62, 30, 255), width=14))

    def front_rim():
        ic.overlay(lambda d: d.arc((x0, y0, x1, y1), 8, 172, fill=(176, 136, 80, 255), width=14))
        ic.overlay(lambda d: d.arc((x0 + 3, y0 - 4, x1 - 3, y1 - 4), 30, 150, fill=(236, 204, 146, 170), width=4))
        ic.overlay(lambda d: d.arc((x0 - 2, y0 - 2, x1 + 2, y1 + 2), 0, 360, fill=(40, 26, 12, 200), width=3))

    return inner, front_rim


def mountage(ic: Icon, cx, base, h, w, cocoon_items) -> None:
    """Straw mountage: a bristly bundle of twigs and straw tied at the waist and splayed at the top,
    with cocoons spun into it."""
    rnd = ic.random
    tie = base - h * 0.42
    for _ in range(90):
        f = rnd.uniform(-1, 1)
        top = (cx + f * w * 0.55 + rnd.uniform(-10, 10), base - h + abs(f) * h * 0.25 + rnd.uniform(-14, 14))
        foot = (cx + f * w * 0.3, base + rnd.uniform(-6, 4))
        waist = (cx + f * w * 0.08, tie)
        tone = rnd.uniform(0.6, 1.1)
        col = scale((196, 160, 92), tone)
        ic.line([foot, waist, top], 4, col)
        if rnd.random() < 0.3:
            ic.line([waist, top], 2, (246, 222, 160, 150))
    ic.shade(ic.mask("ellipse", (cx - w * 0.1, base - h, cx + w * 0.7, base)), (30, 20, 8), 0.3, blur=18)
    ic.line([(cx - w * 0.12, tie), (cx + w * 0.12, tie + 3)], 10, (90, 62, 30))
    ic.line([(cx - w * 0.12, tie - 3), (cx + w * 0.1, tie)], 3, (200, 160, 100, 180))
    for it in cocoon_items:
        peanut(ic, *it)


def mleaf2(ic: Icon, base, deg: float, length: float, lit: float) -> None:
    """Large glossy mulberry leaf: heart-shaped with a serrated edge, tone set by ``lit`` (0 shade .. 1 sun),
    a darker shadow half, a pale midrib and a small gloss streak."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 30)
    hw = [length * 0.46 * (math.sin(math.pi * min(1, t * 1.05)) ** 0.6) * (1 - 0.4 * t) for t in ts]
    spine = [b + d * length * t for t in ts]
    s1 = [p + n * w * (1.1 if k % 2 else 0.94) for k, (p, w) in enumerate(zip(spine, hw))]
    s2 = [p - n * w * (1.1 if k % 2 else 0.94) for k, (p, w) in enumerate(zip(spine, hw))]
    lobe = [b - d * length * 0.06 + n * length * 0.12, b - d * length * 0.02, b - d * length * 0.06 - n * length * 0.12]
    pts = [tuple(p) for p in s1 + s2[::-1]] + [tuple(p) for p in lobe[::-1]]
    c1 = tuple(int(v) for v in np.array((30, 50, 16)) + lit * np.array((116, 124, 50)))
    c2 = tuple(int(v) for v in np.array((10, 20, 6)) + lit * np.array((50, 66, 20)))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, radial=(min(xs), min(ys), length * 1.3), noise=0.16, chroma=0.1)
    lower = s1 if n[1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (6, 12, 2), 0.3)
    ic.line([tuple(p) for p in spine[1:-4]], 2, (180, 204, 130, int(20 + 60 * lit)))
    if lit > 0.5:
        g0, g1 = spine[6] + n * hw[6] * 0.4, spine[14] + n * hw[14] * 0.45
        ic.line([tuple(g0), tuple(g1)], 4, (240, 250, 210, int(90 * lit)))
    ic.outline(pts, 2, (12, 24, 6, int(40 + 70 * lit)))


def mulberry_crown(ic: Icon, cx, cy, rx, ry, fruit: int = 6, leaves: int = 60, seed_shift: float = 0.0) -> Image.Image:
    """Mulberry crown painted as a volume lit from the upper left: lumpy mass with a lit upper-left,
    a dark core and underside, large serrated leaves breaking the outline, a few dark fruit clusters."""
    rnd = ic.random
    m = blank()
    md = ImageDraw.Draw(m)
    for _ in range(13):
        u = rnd.uniform(-0.72, 0.72)
        bx, by = cx + u * rx, cy + rnd.uniform(-0.45, 0.3) * ry * (1 - abs(u) * 0.5)
        br = rnd.uniform(0.5, 0.64) * ry
        md.ellipse((bx - br * 1.2, by - br, bx + br * 1.2, by + br), fill=255)
    ic.fill(m, "#5e8a32", "#0e1a08", radial=(cx - rx * 0.6, cy - ry * 0.8, max(rx, ry) * 1.8), noise=0.28, chroma=0.12)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.5, cy - ry * 0.2, cx + rx * 1.2, cy + ry * 1.4)), m, (4, 10, 2), 0.5, 34)
    tint(ic, ic.mask("ellipse", (cx - rx * 1.1, cy - ry * 1.2, cx + rx * 0.2, cy + ry * 0.05)), m, (230, 240, 150), 0.16, 34)
    items = []
    for _ in range(leaves):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.random() ** 0.5
        x = cx + math.cos(a) * rx * rr * 0.98
        y = cy + math.sin(a) * ry * rr * (0.95 if math.sin(a) < 0 else 0.7)
        lit = 0.6 - (x - cx) / (rx * 1.2) - (y - cy) / (ry * 1.0) + rnd.uniform(-0.15, 0.15)
        lit = max(0.0, min(1.0, lit)) ** 1.2
        size = rnd.uniform(46, 62) if rr > 0.8 else rnd.uniform(32, 46)
        items.append((lit, x, y, math.degrees(a) + rnd.uniform(-50, 50), size))
    items.sort(key=lambda it: it[0])  # shaded leaves first, sunlit ones on top
    for lit, x, y, deg, L in items:
        mleaf2(ic, (x, y), deg, L, lit)
    for _ in range(fruit):
        fx, fy = cx + rnd.uniform(-0.7, 0.6) * rx, cy + rnd.uniform(-0.2, 0.7) * ry

        def berries(d, fx=fx, fy=fy):
            d.line([(fx, fy - 14), (fx + 2, fy - 4)], fill=(60, 80, 30, 255), width=3)
            for k in range(7):
                bx, by = fx + rnd.uniform(-7, 7), fy + k * 3.5 + rnd.uniform(-2, 2)
                d.ellipse((bx - 6, by - 6, bx + 6, by + 6), fill=(58, 12, 34, 255))
                d.ellipse((bx - 4, by - 5, bx, by - 1), fill=(170, 60, 90, 200))

        ic.overlay(berries)
    return m


def skein(ic: Icon, x, top, length, width, colors=("#f0d27c", "#a8802e")) -> None:
    """Skein of reeled silk hanging from a peg: a long glossy loop of fine strands (open in the middle),
    a lit left side, a sheen streak, a tie near the head. Draws its own contact shadow on the wall."""
    ts = np.linspace(0, 1, 26)
    prof = [width / 2 * (0.3 + 0.7 * math.sin(math.pi / 2 * min(1, t / 0.75))) * (1 - 0.5 * max(0, t - 0.8) / 0.2) for t in ts]
    left = [(x - p, top + length * t) for t, p in zip(ts, prof)]
    right = [(x + p, top + length * t) for t, p in zip(ts, prof)]
    pts = left + [(x, top + length + 6)] + right[::-1]
    m = ic.poly_mask(pts)
    ic.shade(ic.poly_mask([(px + 7, py + 7) for px, py in pts]), (30, 20, 10), 0.4, blur=5)
    ic.fill(m, colors[0], colors[1], radial=(x - width * 0.35, top + length * 0.3, length * 0.9), noise=0.12, chroma=0.08)
    ic.shade(ic.poly_mask([(x, top)] + right[1:]), (60, 36, 6), 0.25)

    def strands(d):
        for k in range(9):
            f = -0.85 + k * 0.21
            d.line([(x + p * f, top + length * t) for t, p in zip(ts, prof)], fill=(120, 84, 24, 70), width=2)
        d.line([(x - p * 0.45, top + length * t) for t, p in zip(ts[3:-4], prof[3:-4])], fill=(255, 250, 214, 190), width=4)

    ic.overlay(strands, m)
    ic.line([(x - width * 0.2, top + length * 0.12), (x + width * 0.2, top + length * 0.13)], 6, (150, 104, 40))
    ic.ellipse((x - 8, top - 8, x + 8, top + 8), "#6a4a2c", "#3a2616", edge=3)
    ic.outline(pts, 3, (90, 60, 20, 160))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.70
    ic.grade["mute"] = 0.84

    # ---- rearing house: lime-washed walls, open front with tray shelves, clay-tile roof
    L, R, EAVE, BASE = 360, 880, 460, 820
    wall = plaster(ic, (L, EAVE, R, BASE), "#dccaa4", "#a88e68")
    OX0, OX1 = 500, 820  # the open front
    ic.rect((OX0, 520, OX1, BASE), "#34271b", "#140e09", edge=0)
    tray_rack(ic, OX0 + 14, OX1 - 14, (582, 666, 750))
    ic.shade(ic.mask("rectangle", (OX0, 520, OX1, 580)), alpha=0.45, blur=12)
    for x in (OX0, OX1):
        timber(ic, (x, 506), (x, BASE), 24)
    timber(ic, (OX0 - 12, 516), (OX1 + 12, 516), 24)
    timber(ic, ((OX0 + OX1) / 2, 520), ((OX0 + OX1) / 2, BASE), 16)
    ic.window(398, 560, 450, 616)
    tint(ic, ic.mask("rectangle", (L, EAVE, R, EAVE + 70)), wall, (30, 20, 10), 0.5, 14)
    ic.outline([(L, EAVE), (R, EAVE), (R, BASE), (L, BASE)], 5)
    ic.rect((L - 10, BASE - 14, R + 10, BASE + 8), "#8c8272", "#5a5246")  # stone footing
    pantiles(ic, ((L + 40, 290), (R - 40, 290)), ((L - 46, EAVE + 16), (R + 46, EAVE + 16)), "#b0643c", "#62301a", step=30)
    ic.rect((L + 30, 276, R - 30, 298), "#9a5634", "#5e2e18")  # ridge tiles
    ic.shade(ic.poly_mask([(700, 260), (940, 260), (940, EAVE + 40), (720, EAVE + 40)]), alpha=0.2, blur=50)

    # ---- reeled silk hanging on the wall: skeins on pegs by the window and at the right corner
    skein(ic, 430, 640, 130, 44)
    skein(ic, 858, 560, 120, 30, ("#f4e2b0", "#b09260"))

    # ---- pollarded mulberry on the left: short knobbly trunk, knuckled head, a volumetric crown
    trunk = [(150, 904), (176, 862), (184, 800), (174, 740), (188, 690), (178, 640), (196, 606), (250, 604), (262, 650),
             (252, 700), (266, 760), (258, 830), (270, 870), (300, 904)]
    ic.poly(trunk, "#a08868", "#2e2218", span=(150, 300), vertical=False, noise=0.34, edge=3)
    for x0 in (198, 218, 240):  # bark furrows
        ic.line([(x0 + rnd.uniform(-6, 6), 890), (x0 + rnd.uniform(-10, 10), 760), (x0 + rnd.uniform(-8, 8), 620)], 4,
                (40, 30, 20, 130))
    for x, y, r in ((186, 742, 18), (250, 704, 16), (252, 830, 15), (196, 850, 13)):  # knobbly burls: lit top, shaded foot
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.9, x + r, y)), (236, 222, 190), 0.22, blur=4)
        ic.shade(ic.mask("ellipse", (x - r, y, x + r, y + r * 0.9)), (20, 14, 10), 0.35, blur=4)
    for _ in range(14):
        x, y = rnd.uniform(180, 262), rnd.uniform(620, 890)
        light = rnd.random() < 0.4
        ic.shade(ic.mask("ellipse", (x - 9, y - 14, x + 9, y + 14)), (230, 220, 190) if light else (20, 14, 10),
                 0.2 if light else 0.28, blur=3)
    for p0, p1, w in (((206, 646), (110, 570), 22), ((240, 642), (350, 560), 20), ((222, 638), (230, 530), 20)):
        ic.line([p0, p1], w, (84, 66, 50))
    ic.ellipse((180, 618, 270, 662), "#8e765a", "#3a2c1e", edge=3)  # the pollard knuckle
    crown = mulberry_crown(ic, 226, 552, 240, 150, fruit=7, leaves=170)
    ic.shade(ic.mask("rectangle", (140, 650, 300, 750)), (10, 16, 6), 0.4, blur=20)

    # ---- trodden ground under the tree and the baskets
    ic.poly([(90, 884), (240, 866), (400, 870), (380, 910), (240, 922), (110, 912)], "#6e5638", "#4a3a26", noise=0.3,
            edge=3)
    ic.shade(ic.mask("ellipse", (60, 850, 460, 920)), (10, 14, 6), 0.35, blur=16)

    # ---- basket of picked mulberry leaves under the tree
    basket(ic, 300, 860, 450, 990)
    heap = ic.poly_mask(ic.jitter(375, 850, 72, 30, 14, 0.15))
    leaf_bed(ic, heap, (300, 810, 450, 880), n=40)
    ic.overlay(lambda d: d.arc((300, 840, 450, 880), 10, 170, fill=(170, 130, 80, 255), width=9))

    # ---- straw mountage with cocoons spun into it
    ic.shade(ic.mask("ellipse", (450, 970, 620, 1010)), alpha=0.45, blur=8)
    mountage(ic, 530, 996, 190, 120, [(500, 880, 22, 0.5, IVORY), (560, 906, 21, -0.4, GOLD), (520, 938, 20, 0.2, CREAM)])

    # ---- deep round bamboo sieve heaped into a dome of large cocoons, bottom right
    ic.shade(ic.mask("ellipse", (600, 960, 1016, 1016)), alpha=0.5, blur=10)
    inner, front_rim = sieve(ic, 620, 858, 1004, 944, 56)
    rows = ((930, (672, 740, 812, 884, 952)), (900, (706, 780, 856, 928)), (866, (742, 818, 892)), (832, (780, 856)))
    items = []
    for y, xs in rows:
        for x in xs:
            pal = GOLD if rnd.random() < 0.35 else IVORY if rnd.random() < 0.5 else CREAM
            items.append((x + rnd.uniform(-8, 8), y + rnd.uniform(-6, 6), rnd.uniform(34, 40), rnd.uniform(-0.5, 0.5), pal))
    items.sort(key=lambda it: it[1])
    with ic.clipped(union(inner, ic.mask("rectangle", (0, 0, SIZE, 901)))):  # the front row sits inside the rim
        for it in items:
            peanut(ic, *it)
    ic.shade(ic.mask("ellipse", (840, 800, 1060, 1000)), (40, 30, 20), 0.22, blur=30)
    front_rim()
