"""Regulated Sericulture Farm: a long two-storey rearing house with a ventilated ridge, pollarded
mulberry rows, a cocoon-sorting table and a reeling basin on its stove with the silk reel.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/regulated_sericulture_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/regulated_sericulture_farm

Identity: an ordered lime-washed rearing house under a clay-tile roof with a louvred ventilation
lantern along the ridge, its open arcade full of tray shelves; a brick stove with a steaming copper
basin and a spoked reel wound with golden silk at the bottom right; a sorting table of cocoons and a
row of pollarded mulberries on the left. Tier 1 of the sericulture chain: the Silk Farm's small house
and loose basket become a regular rearing house and a reeling station.

Local helpers are shared by the fibre and silk family (cotton, fibre dressing, sericulture).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 47
REFS = ("llotja_seda", "farming_village", "lucca_silk_production_guild", "fruit_orchard")

CREAM = ((226, 218, 190), (250, 246, 230), (150, 138, 108))
IVORY = ((238, 232, 212), (255, 252, 242), (160, 150, 124))
GOLD = ((214, 166, 72), (242, 208, 126), (126, 90, 32))
GOLD2 = ((200, 146, 56), (236, 194, 106), (116, 78, 26))
SILK = (("#e8c878", "#9a7430"), ("#f0d690", "#a68040"), ("#dcb866", "#8a6428"))


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


def tray_rack(ic: Icon, x0, x1, tops, depth: float = 22) -> None:
    """Shelves of shallow rearing trays: a thin wooden front lip, green leaf bed with worms on top."""
    for y in tops:
        top = ic.poly_mask([(x0 + 6, y - depth), (x1 - 6, y - depth), (x1, y), (x0, y)])
        leaf_bed(ic, top, (x0, y - depth, x1, y), n=int((x1 - x0) / 5))
        worms(ic, top, (x0 + 8, y - depth + 4, x1 - 8, y - 4), int((x1 - x0) / 20))
        ic.rect((x0 - 4, y, x1 + 4, y + 14), "#b08658", "#6a4a2c", edge=4)


def pollard(ic: Icon, cx: float, base: float, h: float, r: float) -> None:
    """Pollarded mulberry: stout trunk, a knuckle of short limbs, a dense round head of big leaves."""
    rnd = ic.random
    top = base - h
    trunk = [(cx - 36, base), (cx - 26, base - 30), (cx - 24, top + 30), (cx - 40, top), (cx + 40, top), (cx + 26, top + 30),
             (cx + 28, base - 30), (cx + 40, base)]
    ic.poly(trunk, "#9a8062", "#2e2218", span=(cx - 34, cx + 34), vertical=False, noise=0.32, edge=3)
    for dx in (-60, -20, 25, 64):
        ic.line([(cx + dx * 0.2, top + 10), (cx + dx, top - r * 0.6)], 14, (84, 66, 50))
    crown = canopy(ic, cx, top - r * 0.55, r, r * 0.8, light="#72a03e", dark="#1c3210", blobs=16, dab=(7, 13))
    for _ in range(10):
        a = rnd.uniform(math.pi * 1.05, math.pi * 1.95)
        mleaf(ic, (cx + math.cos(a) * r * 0.8, top - r * 0.55 + math.sin(a) * r * 0.65), math.degrees(a) + rnd.uniform(-30, 30),
              rnd.uniform(34, 44))
    ic.shade(ic.intersect(crown, ic.mask("ellipse", (cx - r * 1.2, top - r * 1.6, cx + r * 0.2, top - r * 0.5))),
             (255, 244, 210), 0.14, blur=24)


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


def pollard2(ic: Icon, cx: float, base: float, h: float, rx: float, ry: float) -> None:
    """Pollarded mulberry: short knobbly trunk, a swollen knuckled head, straight new shoots rising
    from it (some above the crown) and a volumetric crown of large leaves with fruit."""
    rnd = ic.random
    top = base - h * 0.52
    trunk = [(cx - 40, base), (cx - 28, base - 34), (cx - 34, base - h * 0.3), (cx - 26, top + 34), (cx - 46, top + 6),
             (cx - 30, top - 14), (cx + 34, top - 12), (cx + 48, top + 8), (cx + 28, top + 34), (cx + 34, base - h * 0.28),
             (cx + 28, base - 34), (cx + 44, base)]
    ic.poly(trunk, "#a08868", "#2e2218", span=(cx - 44, cx + 44), vertical=False, noise=0.34, edge=3)
    for _ in range(9):
        x, y = cx + rnd.uniform(-26, 26), rnd.uniform(top, base - 10)
        light = rnd.random() < 0.4
        ic.shade(ic.mask("ellipse", (x - 8, y - 12, x + 8, y + 12)), (230, 220, 190) if light else (20, 14, 10),
                 0.2 if light else 0.3, blur=3)
    for dx in (-30, 0, 30):  # knuckles of the pollard head
        k = (cx + dx, top - 6 + abs(dx) * 0.3)
        ic.ellipse((k[0] - 22, k[1] - 16, k[0] + 22, k[1] + 16), "#a88e6c", "#3e2e20", edge=3)
    shoots = []
    for _ in range(9):
        x0 = cx + rnd.uniform(-34, 34)
        tip = (x0 + (x0 - cx) * rnd.uniform(1.5, 3.5), top - ry * rnd.uniform(1.6, 2.35))
        shoots.append(((x0, top - 12), tip))
        ic.line([(x0, top - 12), tip], 6, (96, 72, 48))
    mulberry_crown(ic, cx, top - ry * 0.85, rx, ry, fruit=4, leaves=int(rx * ry / 150))
    for p0, tip in shoots[:4]:  # whips standing out of the crown with a few small leaves
        ic.line([((p0[0] + tip[0]) / 2, (p0[1] + tip[1]) / 2 - 20), tip], 5, (104, 80, 52))
        for t in (0.75, 0.9):
            lx, ly = p0[0] + (tip[0] - p0[0]) * t, p0[1] + (tip[1] - p0[1]) * t
            mleaf2(ic, (lx, ly), rnd.choice((-40, -140)) + rnd.uniform(-15, 15), 26, 0.8)


def steam2(ic: Icon, x: float, y: float, h: float, w: float = 44) -> None:
    """Tall warm-grey steam column: soft body puffs with a lit left edge, drifting as it rises."""
    rnd = ic.random
    for k in range(9):
        t = k / 8
        cx = x + math.sin(t * 3.4) * w * 0.6 + t * 20
        cy = y - h * t
        r = w * (0.5 + 0.8 * t)
        ic.shade(ic.mask("ellipse", (cx - r, cy - r * 0.75, cx + r, cy + r * 0.75)), (176, 166, 152), 0.42 * (1 - t * 0.55),
                 blur=10)
        ic.shade(ic.mask("ellipse", (cx - r * 0.95, cy - r * 0.7, cx - r * 0.1, cy + r * 0.2)), (252, 248, 236),
                 0.4 * (1 - t * 0.6), blur=7)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.70
    ic.grade["mute"] = 0.84

    # ---- rearing house: two storeys, open arcade of tray shelves below, shuttered windows above
    L, R, EAVE, FLOOR, BASE = 250, 960, 380, 590, 830
    wall = plaster(ic, (L, EAVE, R, BASE), "#e2d2b0", "#ab9270")
    bays = np.linspace(L + 30, R - 30, 5)
    for i in range(4):  # ground floor: open bays with tray shelves
        x0, x1 = bays[i] + 18, bays[i + 1] - 18
        arch = union(ic.mask("ellipse", (x0, 624, x1, 700)), ic.mask("rectangle", (x0, 662, x1, BASE)))
        ic.fill(arch, "#34271b", "#140e09", (624, BASE), noise=0.16)
        tray_rack(ic, x0 + 10, x1 - 10, (712, 772, 820))
        ic.shade(ic.intersect(arch, ic.mask("rectangle", (x0, 620, x1, 710))), alpha=0.5, blur=10)
        ic.overlay(lambda d, b=(x0, 624, x1, 700): d.arc(b, 180, 360, fill=(90, 70, 50, 200), width=6))
    for x in bays:  # piers with stone quoins
        ic.rect((x - 18, 620, x + 18, BASE), "#cfbf9c", "#9a8664", vertical=False, edge=4)
    timber(ic, (L, FLOOR), (R, FLOOR), 20, "#b2a282", "#7a6a50")  # string course
    for i in range(5):  # upper floor: evenly spaced shuttered openings, trays glimpsed inside
        cx = L + 70 + i * (R - L - 140) / 4
        ic.rect((cx - 34, 440, cx + 34, 540), "#34271b", "#140e09", edge=4)
        for y in (476, 510):
            ic.rect((cx - 30, y, cx + 30, y + 8), "#6a8e3c", "#2c4414", edge=0)
        for sx in (cx - 34 - 36, cx + 34):
            ic.rect((sx, 440, sx + 36, 540), "#6e7e5c", "#3e4a32", edge=4)  # open shutters, faded green
            for y in (460, 490, 520):
                ic.line([(sx + 4, y), (sx + 32, y + 6)], 3, (30, 36, 22, 150))
    tint(ic, ic.mask("rectangle", (L, EAVE, R, EAVE + 60)), wall, (30, 20, 10), 0.5, 14)
    ic.outline([(L, EAVE), (R, EAVE), (R, BASE), (L, BASE)], 5)
    ic.rect((L - 10, BASE - 12, R + 10, BASE + 10), "#8c8272", "#5a5246")  # stone footing

    # ---- roof with the louvred ventilation lantern along the ridge
    pantiles(ic, ((L + 40, 214), (R - 40, 214)), ((L - 44, EAVE + 16), (R + 44, EAVE + 16)), "#b0643c", "#62301a", step=30)
    VL, VR = 440, 780
    ic.rect((VL, 150, VR, 214), "#3a2a1c", "#1a120c", edge=4)
    for x in np.arange(VL + 12, VR, 24):
        ic.line([(x, 154), (x, 212)], 10, (132, 98, 64))
    pantiles(ic, ((VL + 24, 108), (VR - 24, 108)), ((VL - 34, 160), (VR + 34, 160)), "#b8703f", "#6a3620", step=26, edge=5)
    ic.rect((L + 30, 204, R - 30, 222), "#9a5634", "#5e2e18")
    ic.shade(ic.poly_mask([(760, 100), (1010, 100), (1010, EAVE + 40), (790, EAVE + 40)]), alpha=0.2, blur=50)

    # ---- pollarded mulberry row on the left, staggered in depth: knobbly stumps, knuckled heads, new shoots
    ic.shade(ic.mask("ellipse", (10, 850, 330, 930)), alpha=0.35, blur=12)
    pollard2(ic, 170, 884, 300, 164, 138)
    pollard2(ic, 318, 928, 250, 138, 114)

    # ---- cocoon sorting table: white cocoons heaped on the left, golden ones on the right
    ic.shade(ic.mask("ellipse", (300, 960, 640, 1010)), alpha=0.4, blur=10)
    for x in (330, 610):
        timber(ic, (x, 920), (x, 996), 20)
    top = ic.poly_mask([(318, 880), (628, 880), (640, 922), (306, 922)])
    ic.fill(top, "#b08658", "#6a4a2c", (880, 922), noise=0.2)
    ic.line([(318, 882), (628, 882)], 4, (230, 196, 150, 160))
    for heap_x, pals in ((392, (IVORY, CREAM, IVORY)), (548, (GOLD, GOLD, GOLD2))):
        spots = [(-50, 902), (-4, 906), (44, 900), (-28, 880), (22, 878), (-4, 856)]
        its = [(heap_x + dx + rnd.uniform(-5, 5), y + rnd.uniform(-3, 3), rnd.uniform(24, 27), rnd.uniform(-0.5, 0.5),
                pals[k % 3]) for k, (dx, y) in enumerate(spots)]
        ic.shade(ic.mask("ellipse", (heap_x - 80, 880, heap_x + 80, 924)), (30, 20, 10), 0.4, blur=8)
        for it in sorted(its, key=lambda it: it[1]):
            peanut(ic, *it, halo=False)
    ic.rect((304, 922, 642, 940), "#9a7450", "#5e4028", edge=4)

    # ---- reeling station: brick stove, copper basin with steam, spoked reel of golden silk
    SX0, SX1, ST = 670, 850, 880
    stove = ic.mask("rectangle", (SX0, ST, SX1, 1000))
    ic.fill(stove, "#a0644a", "#5a3426", (ST, 1000), noise=0.24)

    def bricks(d):
        y, k = ST, 0
        while y < 1000:
            d.line([(SX0, y), (SX1, y)], fill=(210, 180, 150, 70), width=3)
            for x in np.arange(SX0 - (k % 2) * 20, SX1, 40):
                d.line([(x, y), (x, y + 20)], fill=(210, 180, 150, 60), width=3)
            y += 20
            k += 1

    ic.overlay(bricks, stove)
    ic.fill(ic.mask("ellipse", (732, 950, 790, 996)), "#e08a3a", "#6e2410", radial=(760, 980, 36))  # fire mouth
    tint(ic, ic.mask("rectangle", (SX1 - 50, ST, SX1 + 20, 1000)), stove, (20, 10, 6), 0.35, 12)
    ic.outline([(SX0, ST), (SX1, ST), (SX1, 1000), (SX0, 1000)], 5)
    ic.fill(ic.mask("ellipse", (SX0 - 14, 846, SX1 + 14, 912)), "#c07a44", "#6a3418", radial=(SX0, 846, 220))  # basin
    ic.fill(ic.mask("ellipse", (SX0 + 6, 852, SX1 - 6, 900)), "#8a8a74", "#4a4a3a", (852, 900), noise=0.1)  # hot water
    for k in range(4):
        peanut(ic, SX0 + 40 + k * 32 + rnd.uniform(-6, 6), 874 + rnd.uniform(-6, 8), 17, rnd.uniform(-0.5, 0.5), IVORY, halo=False)
    ic.overlay(lambda d: d.ellipse((SX0 - 14, 846, SX1 + 14, 912), outline=(70, 36, 16, 230), width=6))
    ic.overlay(lambda d: d.arc((SX0 - 8, 850, SX1 + 8, 908), 190, 300, fill=(240, 190, 140, 150), width=4))
    steam2(ic, 700, 858, 280, 46)  # rises in front of the dark arcade bay
    # the reel: two posts, a spoked wheel wound with glossy golden silk, threads from the basin
    timber(ic, (884, 790), (884, 1000), 18)
    timber(ic, (1010, 596), (1010, 1000), 18)
    ic.line([(800, 868), (948, 820)], 3, (255, 236, 170, 230))
    ic.line([(812, 872), (950, 832)], 2, (255, 236, 170, 210))
    wheel(ic, 948, 822, 78, spokes=6, rim=12)
    ring = ImageChops.subtract(ic.mask("ellipse", (948 - 70, 822 - 70, 948 + 70, 822 + 70)),
                               ic.mask("ellipse", (948 - 44, 822 - 44, 948 + 44, 822 + 44)))
    ic.fill(ring, "#f8da7c", "#a07020", radial=(905, 775, 170), noise=0.1, chroma=0.12)

    def strands(d):
        for k in range(12):
            rr = 46 + k * 2.0
            d.ellipse((948 - rr, 822 - rr, 948 + rr, 822 + rr), outline=(255, 244, 200, 70) if k % 2 else (120, 84, 24, 60),
                      width=2)
        d.arc((948 - 62, 822 - 62, 948 + 62, 822 + 62), 190, 280, fill=(255, 252, 226, 230), width=7)  # sheen
        d.arc((948 - 54, 822 - 54, 948 + 54, 822 + 54), 200, 250, fill=(255, 255, 240, 180), width=3)
        d.arc((948 - 60, 822 - 60, 948 + 60, 822 + 60), 20, 80, fill=(90, 60, 10, 140), width=6)

    ic.overlay(strands, ring)
    ic.overlay(lambda d: d.ellipse((948 - 70, 822 - 70, 948 + 70, 822 + 70), outline=(90, 60, 20, 200), width=3))
    ic.ellipse((936, 810, 960, 834), "#8a6440", "#4a3220", edge=3)
    # skeins of reeled silk hung on a rod beside the reel
    for k, x in enumerate((890, 936, 982)):
        hank(ic, x, 606, 104, 32, SILK[k % 3], sway=0.02)
    timber(ic, (860, 604), (1020, 604), 14)
