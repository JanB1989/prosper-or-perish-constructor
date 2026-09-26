"""Fiber Dressing Yard: a retting pond with sunken flax bundles, drying stooks, an open drying shed
hung with dressed fibre, a hackling bench.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/fiber_dressing_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/fiber_dressing_yard

Identity: rows of long pale-blond fibre stricks hanging in an open, thatched drying shed; golden
flax stooks on the left; a murky clay-banked retting pond in front with bundles weighed down by
stones; a hackling bench with an iron-toothed hackle and a hank of dressed fibre at the bottom
right. Tier 1 over the vanilla fiber crops farm: the yard that turns stalks into fibre.

Local helpers are shared by the fibre and silk family (cotton, fibre dressing, sericulture).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("fiber_crops_farm", "farming_village", "cotton_plantation", "sheep_farms")

FIBRE = (("#d8c07e", "#8a7038"), ("#ccb070", "#7a602c"), ("#e2cc92", "#967c44"), ("#c4a462", "#6e5626"))


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
    # volume: warmer and darker towards the eaves, weathered streaks, lit ridge, shaded eave band
    y_r = min(p[1] for p in ridge)
    y_e = max(p[1] for p in eave)
    tint(ic, ic.mask("rectangle", (0, y_r + (y_e - y_r) * 0.4, SIZE, y_e + 10)), m, (96, 48, 12), 0.42, 30)
    tint(ic, ic.mask("rectangle", (0, y_e - (y_e - y_r) * 0.2, SIZE, y_e + 10)), m, (40, 22, 8), 0.45, 14)
    for f in (0.2 + rnd.uniform(-0.05, 0.05), 0.52 + rnd.uniform(-0.05, 0.05), 0.8 + rnd.uniform(-0.05, 0.05)):
        top = np.array(ridge[0], float) + (np.array(ridge[-1], float) - np.array(ridge[0], float)) * f
        bot = np.array(eave[0], float) + (np.array(eave[-1], float) - np.array(eave[0], float)) * (f + rnd.uniform(-0.04, 0.04))
        wv = rnd.uniform(14, 26)
        streak = [tuple(top + [-wv * 0.4, 30]), tuple(top + [wv * 0.4, 30]), tuple(bot + [wv, 0]), tuple(bot + [-wv, 0])]
        tint(ic, ic.poly_mask(streak), m, (44, 30, 12), 0.3, 6)
    tint(ic, ic.mask("rectangle", (0, y_r - 20, SIZE, y_r + (y_e - y_r) * 0.22)), m, (250, 226, 160), 0.18, 22)
    ic.line([tuple(p) for p in ridge], 22, (132, 106, 60))
    ic.line([(p[0], p[1] - 3) for p in ridge], 9, (214, 188, 128, 200))
    ic.shade(ic.poly_mask(lip), (30, 16, 6), 0.28)
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


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.70
    ic.grade["mute"] = 0.84

    # ---- open drying shed: dark interior, rails hung with fibre stricks, posts, thatch
    L, R, EAVE, BASE = 330, 990, 448, 840
    ic.rect((L, EAVE, R, BASE), "#34271b", "#15100a", edge=0)
    y = 490
    for j, x in enumerate(np.arange(L + 40, R - 24, 50)):
        c = FIBRE[(j * 3) % len(FIBRE)]
        hank(ic, x + rnd.uniform(-5, 5), y - 6, 250 + rnd.uniform(-50, 30), 40, c, sway=rnd.uniform(-0.03, 0.03))
    timber(ic, (L, y), (R, y), 20)
    # dressed fibre and tow piled on the shed floor
    for x in np.arange(L + 60, R - 40, 90):
        ic.fill(ic.poly_mask(ic.jitter(x, 818, 54, 20, 12, 0.15)), "#a8905c", "#4e3e20", radial=(x - 30, 800, 80), noise=0.3)
    ic.shade(ic.mask("rectangle", (L, EAVE, R, EAVE + 110)), alpha=0.7, blur=18)
    for x in (L + 10, 660, R - 10):
        timber(ic, (x, EAVE - 10), (x, BASE), 26)
    ridge = [(376, 246), (660, 236), (948, 248)]
    eave = [(x, EAVE + rnd.uniform(-5, 7)) for x in np.linspace(296, 1024, 20)]
    thatch(ic, ridge, eave, ("#9c8050", "#4e3c20"))
    tint(ic, ic.poly_mask([(700, 220), (1030, 220), (1030, 490), (740, 490)]), None, (30, 40, 60), 0.2, 50)
    tint(ic, ic.poly_mask([(300, 220), (560, 220), (520, 490), (290, 490)]), None, (150, 90, 30), 0.14, 50)

    # ---- flax stooks drying on the left
    ic.shade(ic.mask("ellipse", (10, 800, 360, 860)), alpha=0.4, blur=12)
    stook(ic, 110, 836, 360, 180)
    stook(ic, 262, 848, 310, 160)

    # ---- retting pond: a sunken, irregular pit of murky water, bundles weighed down with fieldstones
    far = [(40, 892), (120, 878), (230, 884), (340, 872), (450, 880), (560, 874), (650, 890)]
    near = [(668, 930), (600, 956), (500, 948), (400, 966), (300, 954), (190, 970), (90, 956), (30, 934)]
    pond = far + near
    pm = ic.poly_mask(pond)
    ic.fill(pm, "#262a14", "#66704a", (874, 972), noise=0.22, chroma=0.12)
    # the far bank drops into the water: a dark earth lip and its shadow on the surface
    tint(ic, ic.mask("rectangle", (0, 860, SIZE, 904)), pm, (10, 10, 4), 0.6, 10)
    for foot, head in (((120, 930), (330, 916)), ((290, 954), (560, 940)), ((380, 908), (600, 904))):
        sm = sheaf(ic, foot, head, 44, ("#a89252", "#4a3e1a"), seeds=False)
        wl = (foot[1] + head[1]) / 2 + 3  # water line: the lower half sinks under murky water
        under = ic.intersect(sm, ic.mask("rectangle", (0, wl, SIZE, SIZE)))
        ic.fill(under, "#3a4228", "#262c18", (wl, wl + 30), noise=0.2)
        ic.shade(under, (60, 58, 30), 0.25)
        ic.line([(min(foot[0], head[0]) - 6, wl), (max(foot[0], head[0]) + 6, wl - 2)], 3, (170, 176, 130, 150))

    def ripples(d):
        for _ in range(16):
            x, y = rnd.uniform(90, 620), rnd.uniform(900, 960)
            L = rnd.uniform(20, 50)
            d.line([(x, y), (x + L, y)], fill=(150, 156, 120, 70), width=3)
            d.line([(x + 6, y + 5), (x + L - 6, y + 5)], fill=(14, 16, 8, 80), width=3)

    ic.overlay(ripples, pm)
    # rounded fieldstones on the bundles: wet contact shadow, lit top-left, dark underside
    for x, y, r in ((214, 904, 24), (446, 930, 26), (506, 884, 21)):
        ic.shade(ic.mask("ellipse", (x - r * 1.2, y + r * 0.2, x + r * 1.4, y + r * 0.9)), (20, 18, 8), 0.6, blur=5)
        sp = ic.jitter(x, y, r * 1.1, r * 0.8, 18, 0.05)
        smk = ic.poly_mask(sp)
        ic.fill(smk, "#a89a86", "#3a342a", radial=(x - r * 0.6, y - r * 0.6, r * 2.1), noise=0.25, chroma=0.1)
        tint(ic, ic.mask("ellipse", (x - r * 1.2, y + r * 0.1, x + r * 1.2, y + r * 1.2)), smk, (20, 16, 10), 0.4, 4)
        tint(ic, ic.mask("ellipse", (x - r * 0.7, y - r * 0.7, x, y - r * 0.2)), smk, (255, 246, 226), 0.3, 3)
        ic.outline(sp, 3, (36, 30, 22, 170))
    # sloping muddy front bank with a ragged top, grass tufts hiding stretches of the water's edge
    bank = [(p[0], p[1] - 4 + rnd.uniform(-6, 4)) for p in near[::-1]]
    bank = [(10, 940)] + bank + [(690, 928), (704, 958), (650, 982), (600, 972), (540, 996), (460, 978), (390, 990),
                                 (300, 1004), (230, 984), (160, 994), (90, 978), (40, 992), (6, 962)]
    bm = ic.poly_mask(bank)
    ic.fill(bm, "#7a5e3c", "#3e2e1a", (930, 1000), noise=0.34, chroma=0.12)
    tint(ic, ic.mask("rectangle", (0, 920, SIZE, 952)), bm, (24, 18, 8), 0.4, 8)  # wet, darker upper edge

    def mud(d):
        for _ in range(40):
            x, y = rnd.uniform(20, 680), rnd.uniform(950, 995)
            r = rnd.uniform(4, 10)
            d.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.5), fill=(24, 16, 8, 80))
            d.ellipse((x - r * 0.8, y - r * 0.6, x + r * 0.3, y), fill=(170, 136, 94, 80))

    ic.overlay(mud, bm)

    def tuft(x, base, hgt, n=14):
        for _ in range(n):
            tx = x + rnd.uniform(-30, 30)
            top = (tx + rnd.uniform(-22, 22), base - hgt * rnd.uniform(0.5, 1))
            ic.line([(x + rnd.uniform(-14, 14), base), top], 5, (58, 74, 30))
            ic.line([(top[0] - 1, top[1] + 2), ((top[0] + x) / 2, (top[1] + base) / 2)], 2, (150, 170, 90, 140))

    for x, base, hgt in ((110, 980, 60), (330, 986, 52), (520, 976, 58), (250, 992, 40)):
        tuft(x, base, hgt)
    for x0, n in ((30, 14), (610, 12)):  # tall reeds at both ends of the pond, rising well above the water
        for _ in range(n):
            x = x0 + rnd.uniform(0, 64)
            hgt = rnd.uniform(130, 240)
            tip = (x + rnd.uniform(-26, 26), 970 - hgt)
            ic.line([(x, 972), tip], 7, (66, 82, 34))
            ic.line([(x - 1, 968), (tip[0] - 1, tip[1] + 6)], 2, (156, 176, 96, 150))
        for _ in range(3):  # a few seed heads
            x = x0 + rnd.uniform(6, 58)
            y = 970 - rnd.uniform(170, 230)
            ic.ellipse((x - 7, y - 22, x + 7, y + 22), "#6a4a2a", "#3a2614", edge=3)

    # ---- hackling bench, bottom right: a heavy bench, dense iron hackle, a golden dressed hank, tow below
    ic.shade(ic.mask("ellipse", (680, 960, 1020, 1012)), alpha=0.5, blur=10)
    tow = ic.jitter(850, 980, 110, 28, 16, 0.2)
    ic.fill(ic.poly_mask(tow), "#bca676", "#6e5a34", radial=(790, 950, 200), noise=0.3)
    for x in (724, 968):
        timber(ic, (x, 880), (x + (12 if x < 800 else -12), 1004), 40, "#8e6844", "#4a3220")
    top = [(684, 850), (1016, 842), (1006, 868), (692, 876)]
    ic.poly(top, "#c09a68", "#9a7448", noise=0.2, edge=0)  # the lit top plane
    front = [(692, 876), (1006, 868), (1006, 906), (692, 914)]
    ic.poly(front, "#7a5634", "#4a321c", noise=0.22, edge=0)
    ic.line([(690, 875), (1008, 867)], 4, (240, 210, 160, 150))
    ic.outline(top[:2] + [(1006, 906), (692, 914)], 5, (40, 26, 16, 200))
    ic.rect((796, 818, 934, 850), "#8a6440", "#4a3220", edge=4)  # hackle board
    ic.line([(798, 820), (932, 820)], 3, (220, 190, 140, 150))

    def teeth(d):
        for x in np.arange(806, 930, 11):
            d.polygon([(x - 3, 826), (x + 4, 826), (x + 2, 762)], fill=(30, 30, 34, 255))
            d.line([(x - 1, 822), (x + 1, 772)], fill=(190, 190, 196, 190), width=2)

    ic.overlay(teeth)
    sheaf(ic, (700, 850), (790, 842), 34, FIBRE[0], seeds=False)  # strick on the bench, waiting to be drawn
    hank(ic, 978, 832, 170, 74, ("#f4ca56", "#9a6c1c"), sway=0.05)  # golden dressed hank over the bench end
    ic.line([(950, 836), (1006, 834)], 6, (255, 236, 170, 150))
