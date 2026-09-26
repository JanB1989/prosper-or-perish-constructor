"""Herb Gatherers' Grove (simplers_grove): at a woodland edge, a bark-roofed drying shelter hung with
bunches of herbs and flowers, baskets of gathered simples and a sorting table of roots and bark.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/simplers_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/simplers_grove

Identity: the row of herb bunches hanging head-down from the pole of an open drying shelter, each a
different colour (green mint and sage, purple lavender, yellow tansy, white yarrow, a string of
roots), under a lean-to roof of bark slabs on rough forked posts. Behind on the left the dark edge
of the wood (an oak and a pale birch) where the simples are gathered; ferns and wild flowers in the
meadow; in front two wicker baskets of fresh herbs and a trestle with strips of bark and roots.
Not the vanilla apothecary (mortar), not an orchard (no fruit trees, no rows).

Local helpers: the orchard-family helpers of ``nursery_orchard`` (``crown``, ``leaf_dabs``,
``timber``, ``tint``) plus ``bunch`` (hanging herb bunch), ``bark_roof`` (lean-to of bark slabs),
``pole`` (rough round pole), ``fern``, ``flowers`` (meadow flowers), ``basket_of`` (basket heaped
with herbs), ``root`` and ``bark_strip``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 59
REFS = ("apothecary", "forest_village", "fruit_orchard", "farming_village")

LEAF = ("#58783a", "#142410")
BIRCH = ("#a0b050", "#34461a")
WOOD = ("#46644a", "#0c1810")


# ---------------------------------------------------------------- helpers
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def scaled(c, f: float):
    return tuple(int(max(0, min(255, v * f))) for v in rgb(c))


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles/shingles: per-piece tone, lit lower lip, soft course shadow."""
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


def planks(ic: Icon, pts, c1="#86603e", c2="#4e3522", board: float = 26) -> Image.Image:
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
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> None:
    """Squared beam: lit upper half, darker lower half, a grain highlight."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def leaf_dabs(ic: Icon, cx, cy, rx, ry, mask, n: int, colors=LEAF) -> None:
    """Oval leaves over a crown: pale lit leaves on the upper left, dark ones in the shade."""
    rnd = ic.random
    lit = scaled(colors[0], 1.35)
    mid = scaled(colors[0], 0.95)
    dk = scaled(colors[1], 0.9)

    def paint(dr):
        for _ in range(n):
            a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.55
            x, y = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
            v = (y - cy) / ry + 0.6 * (x - cx) / rx
            if v < rnd.uniform(-1.1, 0.1):
                col = lit + (150,)
            elif v < rnd.uniform(-0.1, 1.0):
                col = mid + (150,)
            else:
                col = dk + (160,)
            ang = rnd.uniform(0, 2 * math.pi)
            L = rnd.uniform(12, 20)
            c, s = math.cos(ang), math.sin(ang)
            dr.polygon([(x, y), (x + c * L * 0.5 - s * 5, y + s * L * 0.5 + c * 5), (x + c * L, y + s * L),
                        (x + c * L * 0.5 + s * 5, y + s * L * 0.5 - c * 5)], fill=col)

    ic.overlay(paint, mask)


def crown(ic: Icon, cx, cy, rx, ry, colors=LEAF, n: int = 10, dabs: float = 1.0) -> Image.Image:
    """Leafy crown built from irregular blobs lit from the upper left, leaf dabs, a dark underside and
    a leafy broken edge. Returns the crown mask."""
    rnd = ic.random
    m = blank()
    blobs = []
    for _ in range(n):
        a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.7
        br = min(rx, ry) * rnd.uniform(0.42, 0.62)
        blobs.append((cx + math.cos(a) * (rx - br * 0.8) * r, cy + math.sin(a) * (ry - br * 0.8) * r, br))
    blobs.sort(key=lambda b: b[1])
    for bx, by, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.15, br, 26, 0.10))
        ic.fill(bm, colors[0], colors[1], radial=(bx - br * 0.7, by - br * 0.85, br * 2.3), noise=0.28, chroma=0.12)
        tint(ic, ic.mask("ellipse", (bx - br * 1.2, by + br * 0.2, bx + br * 1.2, by + br * 1.6)), bm, (12, 20, 6), 0.4, 10)
        m = union(m, bm)
    leaf_dabs(ic, cx, cy, rx * 1.05, ry * 1.05, m, int(rx * ry / 40 * dabs), colors)
    tint(ic, ic.mask("ellipse", (cx - rx * 1.1, cy + ry * 0.1, cx + rx * 1.1, cy + ry * 1.4)), m, (10, 18, 6), 0.35, 16)
    # loose leaves sticking out of the edge
    edge = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(15)), m)
    lit, dk = rgb(colors[0]), rgb(colors[1])

    def fringe(dr):
        for _ in range(int((rx + ry) / 7)):
            a = rnd.uniform(0, 2 * math.pi)
            x, y = cx + math.cos(a) * rx * 0.78, cy + math.sin(a) * ry * 0.78
            L = rnd.uniform(9, 15)
            out = a + rnd.uniform(-0.7, 0.7)
            f = 0.35 + 0.5 * max(0.0, -math.sin(a) - 0.3 * math.cos(a))
            col = tuple(int(dk[i] + (lit[i] - dk[i]) * f) for i in range(3)) + (255,)
            dr.line([(x, y), (x + math.cos(out) * L, y + math.sin(out) * L)], fill=col, width=8)

    ic.overlay(fringe, m.filter(ImageFilter.MaxFilter(21)))
    return union(m, edge)


def fruit(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Round shaded fruit (x, y, r, palette) in one blended layer: dark rim, body, lit side, glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in sorted(items, key=lambda it: it[1]):
            dr.ellipse((x - r, y - r, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r + 1.5, y - r + 1, x + r - 2.5, y + r - 3), fill=mid + (255,))
            dr.ellipse((x - r * 0.72, y - r * 0.78, x + r * 0.12, y + r * 0.02), fill=lit + (225,))
            g = max(r * 0.2, 1.6)
            gx, gy = x - r * 0.42, y - r * 0.46
            dr.ellipse((gx - g, gy - g, gx + g, gy + g), fill=(252, 232, 214, 200))

    ic.overlay(paint, clip)


MINT = ((70, 96, 44), (120, 150, 76), (70, 110, 50))  # stems, leaves, heads
SAGE = ((96, 104, 74), (146, 156, 124), (168, 176, 146))
LAVENDER = ((92, 100, 70), (128, 136, 100), (138, 118, 160))
TANSY = ((96, 100, 54), (132, 140, 76), (196, 158, 66))
YARROW = ((84, 100, 56), (130, 146, 90), (226, 220, 196))
POPPY = ((90, 98, 58), (128, 138, 84), (178, 86, 64))


def pole(ic: Icon, p0, p1, w: float, c=("#8a7458", "#3e3022")) -> None:
    """Rough round pole with bark: lit upper edge, dark underside, a few knots."""
    timber(ic, p0, p1, w, c[0], c[1])
    rnd = ic.random
    for _ in range(int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 60)):
        t = rnd.uniform(0.1, 0.9)
        x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        ic.shade(ic.mask("ellipse", (x - w * 0.3, y - w * 0.3, x + w * 0.3, y + w * 0.3)), (20, 14, 8), 0.4, blur=2)


def bunch(ic: Icon, top, w: float, h: float, kind) -> None:
    """Bunch of herbs hung head-down from ``top``: a narrow tied neck, stems widening irregularly
    below it with leaves along them, the (dried, muted) flower colour only at the stem tips, and a
    twine loop to the pole."""
    rnd = ic.random
    stem, leaf, head = kind
    x, y = top
    ic.line([(x, y - 18), (x - 6, y), (x + 6, y)], 4, (180, 160, 110))
    n = int(w * 0.34)
    stems = []
    for i in range(n):
        u = (i / max(n - 1, 1)) * 2 - 1 + rnd.uniform(-0.12, 0.12)
        L = h * rnd.uniform(0.72, 1.0)
        spread = w * 0.5 * (0.75 + 0.35 * rnd.random())
        pts = []
        for t in np.linspace(0, 1, 7):
            px = x + u * 5 + u * spread * (t ** 0.8) + rnd.uniform(-3, 3) * t
            pts.append((px, y + 14 + L * t))
        stems.append((pts, u))
    body = blank()
    ImageDraw.Draw(body).polygon([(x - 8, y + 10), (x + 8, y + 10)] + [s_[0][-1] for s_ in sorted(stems, key=lambda q: -q[1])],
                                 fill=255)
    tips = []

    def strokes(dr):
        for pts, u in stems:  # dark under-strokes give the spray body and depth
            dr.line(pts, fill=tuple(int(v * 0.4) for v in stem) + (255,), width=8)
        for pts, u in stems:
            f = rnd.uniform(0.75, 1.15) * (1.15 - 0.35 * (u + 1) / 2)
            dr.line(pts, fill=tuple(int(min(255, v * f)) for v in stem) + (255,), width=4)
        for pts, u in stems:  # leaves along the lower two thirds of each stem, pointing down and out
            for k in range(2, 6):
                if rnd.random() < 0.25:
                    continue
                lx, ly = pts[k]
                lit = u < 0.2 and rnd.random() < 0.6
                col = tuple(int(min(255, v * (1.1 if lit else 0.62) * rnd.uniform(0.9, 1.1))) for v in leaf) + (255,)
                a = math.atan2(1.0, u * 0.8 + rnd.uniform(-0.9, 0.9))
                L = rnd.uniform(14, 22)
                ex, ey = lx + math.cos(a) * L, ly + math.sin(a) * L
                mx, my = (lx + ex) / 2, (ly + ey) / 2
                dr.polygon([(lx, ly), (mx - math.sin(a) * 5, my + math.cos(a) * 5), (ex, ey),
                            (mx + math.sin(a) * 5, my - math.cos(a) * 5)], fill=col)
            tips.append((pts[-1], u))

    ic.overlay(strokes)

    def florets(dr):
        for (tx, ty), u in tips:
            for _ in range(rnd.randint(2, 4)):
                fx, fy = tx + rnd.uniform(-7, 7), ty + rnd.uniform(-12, 6)
                r = rnd.uniform(4, 6.5)
                f = 1.15 - 0.45 * (u + 1) / 2 + rnd.uniform(-0.12, 0.12)
                dr.ellipse((fx - r - 1, fy - r, fx + r + 1, fy + r + 2), fill=tuple(int(v * 0.4) for v in head) + (190,))
                dr.ellipse((fx - r, fy - r, fx + r, fy + r), fill=tuple(int(max(0, min(255, v * f))) for v in head) + (235,))

    ic.overlay(florets)
    tint(ic, ic.mask("rectangle", (x + w * 0.08, y, x + w, y + h + 30)), body.filter(ImageFilter.MaxFilter(31)),
         (10, 8, 4), 0.3, 10)
    ic.line([(x - 10, y + 12), (x + 10, y + 12)], 9, (170, 146, 96))
    ic.line([(x - 10, y + 9), (x + 6, y + 9)], 3, (220, 200, 150, 170))


def root_string(ic: Icon, top, h: float) -> None:
    """Roots hung up to dry: gnarled pale-brown roots tied by the crown."""
    rnd = ic.random
    x, y = top
    ic.line([(x, y - 18), (x, y)], 4, (180, 160, 110))
    for k in range(4):
        dx = (k - 1.5) * 12
        pts = [(x + dx * 0.3, y + 6)]
        for t in np.linspace(0.2, 1.0, 5):
            pts.append((x + dx * (0.5 + t) + rnd.uniform(-6, 6), y + h * t * rnd.uniform(0.8, 1.0)))
        ic.line(pts, 14 - k, (60, 40, 24))
        ic.line(pts, 10 - k, (168, 128, 86))
        ic.line([(px - 2, py) for px, py in pts[:-1]], 3, (220, 190, 140, 150))
    ic.line([(x - 12, y + 8), (x + 12, y + 8)], 8, (170, 146, 96))


def bark_roof(ic: Icon, pts) -> Image.Image:
    """Lean-to roof of overlapping bark slabs laid down the slope: rough brown-grey, curled edges."""
    rnd = ic.random
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, "#7a6650", "#3e3226", (min(ys), max(ys)), noise=0.3, chroma=0.1)
    (bl, br_, er, el) = (np.array(p, float) for p in pts)
    n = 11
    for k in range(n):
        u0, u1 = k / n, (k + 1) / n + 0.02
        a, b = bl + (br_ - bl) * u0, bl + (br_ - bl) * u1
        c, d = el + (er - el) * u1, el + (er - el) * u0
        slab = ic.intersect(ic.poly_mask([tuple(a), tuple(b), tuple(c), tuple(d)]), m)
        t = rnd.uniform(0.8, 1.15)
        ic.fill(slab, scaled("#8a7660", t), scaled("#453828", t), (min(ys), max(ys)), noise=0.34, chroma=0.12)

        def furrows(dr, a=a, b=b, c=c, d=d):
            for _ in range(8):
                f = rnd.uniform(0.1, 0.9)
                p = a + (b - a) * f
                q = d + (c - d) * f
                dr.line([tuple(p), tuple(q)], fill=(30, 22, 14, 110), width=3)
                dr.line([tuple(p + np.array([-4, 0])), tuple(q + np.array([-4, 0]))], fill=(200, 184, 150, 50), width=2)

        ic.overlay(furrows, slab)
        tint(ic, ic.poly_mask([tuple(b), tuple(b + np.array([14, 0])), tuple(c + np.array([14, 0])), tuple(c)]), m,
             (20, 12, 6), 0.45, 4)
    for _ in range(10):  # moss
        u, v = rnd.random(), rnd.random()
        p = bl + (br_ - bl) * u + ((el + (er - el) * u) - (bl + (br_ - bl) * u)) * v
        r = rnd.uniform(12, 26)
        tint(ic, ic.mask("ellipse", (p[0] - r, p[1] - r * 0.6, p[0] + r, p[1] + r * 0.6)), m, (110, 124, 60), 0.3, 5)
    ic.outline(pts, 5)
    return m


def fern(ic: Icon, x, base, s: float = 1.0, tone: float = 1.0) -> None:
    """Fern clump: arching fronds with pinnae, lit on the left."""
    rnd = ic.random
    for k in range(7):
        a = math.radians(rnd.uniform(-165, -15))
        L = rnd.uniform(70, 110) * s
        pts = [(x + math.cos(a) * L * t + (L * 0.25 * t * t if math.cos(a) > 0 else -L * 0.25 * t * t),
                base + math.sin(a) * L * t + L * 0.45 * t * t) for t in np.linspace(0, 1, 10)]
        lit = math.cos(a) < 0
        col = scaled("#78984a" if lit else "#4a6a2c", tone)
        dk = scaled("#2c4418", tone)
        for i in range(1, 9):
            px, py = pts[i]
            ln = 16 * s * (1 - i / 10)
            ic.line([(px, py), (px - ln * 0.7, py - ln * 0.5)], max(3, int(5 * s)), dk + (230,))
            ic.line([(px, py), (px + ln * 0.7, py - ln * 0.5)], max(3, int(5 * s)), col + (230,))
        ic.line(pts, max(3, int(4 * s)), col + (255,))


def flowers(ic: Icon, clip, box, n: int) -> None:
    """Small wild flowers in the grass: white, yellow, blue-violet dots with a darker centre."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(dr):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            r = rnd.uniform(4, 7) * (0.7 + 0.5 * (y - y0) / max(y1 - y0, 1))
            col = rnd.choice(((236, 232, 214), (232, 196, 70), (150, 126, 196), (226, 226, 220)))
            dr.line([(x, y + r), (x, y + r * 3)], fill=(60, 80, 30, 200), width=3)
            dr.ellipse((x - r, y - r, x + r, y + r), fill=col + (235,))
            dr.ellipse((x - r * 0.35, y - r * 0.35, x + r * 0.35, y + r * 0.35), fill=(150, 120, 40, 235))

    ic.overlay(paint, clip)


def basket_of(ic: Icon, x0, y0, x1, y1, kinds) -> None:
    """Wicker basket heaped with fresh herbs and flower heads."""
    rnd = ic.random
    cx = (x0 + x1) / 2
    ic.shade(ic.mask("ellipse", (x0 - 10, y1 - 20, x1 + 40, y1 + 16)), alpha=0.45, blur=8, clip=False)
    heap = ic.poly_mask(ic.jitter(cx, y0 + 4, (x1 - x0) * 0.5, 40, 16, 0.18))
    ic.fill(heap, "#6e9040", "#243a12", radial=(x0, y0 - 40, (x1 - x0)), noise=0.3)

    def sprigs(dr):
        for _ in range(90):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0 - 44, y0 + 30)
            kind = rnd.choice(kinds)
            if rnd.random() < 0.55:
                col = tuple(int(v * rnd.uniform(0.6, 1.25)) for v in kind[1]) + (230,)
                a = rnd.uniform(0, math.pi)
                dr.line([(x, y), (x + math.cos(a) * 16, y - math.sin(a) * 16)], fill=col, width=7)
            else:
                r = rnd.uniform(4, 7)
                dr.ellipse((x - r, y - r, x + r, y + r), fill=kind[2] + (235,))

    ic.overlay(sprigs, heap)
    ic.basket(x0, y0, x1, y1)


def root(ic: Icon, p0, p1, w: float) -> None:
    ic.line([p0, ((p0[0] + p1[0]) / 2 + 8, (p0[1] + p1[1]) / 2 - 6), p1], int(w + 5), (60, 40, 24))
    ic.line([p0, ((p0[0] + p1[0]) / 2 + 8, (p0[1] + p1[1]) / 2 - 6), p1], int(w), (176, 136, 92))
    ic.line([(p0[0] - 2, p0[1] - 3), ((p0[0] + p1[0]) / 2 + 6, (p0[1] + p1[1]) / 2 - 9)], 3, (230, 200, 150, 150))


def bark_strip(ic: Icon, x, y, L, deg) -> None:
    pts = ic.rotate([(0, -9), (L, -7), (L, 7), (0, 9)], (x, y), deg)
    ic.poly(pts, "#9a7456", "#5a3e28", edge=3)
    inner = ic.rotate([(4, 2), (L - 4, 2), (L - 4, 7), (4, 8)], (x, y), deg)
    ic.poly(inner, "#c49a6a", "#8a6440", edge=0)


# ---------------------------------------------------------------- parts
def shrub(ic: Icon, cx, cy, rx, ry, t: float = 0.6) -> None:
    """Low dark understorey bush."""
    crown(ic, cx, cy, rx, ry, (scaled(WOOD[0], t * 1.2), scaled(WOOD[1], t)), n=6, dabs=0.8)


def woods(ic: Icon) -> None:
    rnd = ic.random
    # the wood behind: one darker, cooler mass from behind the oak to the right edge, bumpy crowns
    # on top, a dark green-brown understorey below them
    top = [(200, 440), (200, 320), (330, 300), (420, 270)]
    top += [(x, 248 + (x - 470) * 0.08 + rnd.uniform(-16, 16)) for x in np.linspace(470, 960, 7)] + [(1004, 330)]
    back_pts = top + [(1004, 900), (200, 900)]
    back = ic.poly_mask(back_pts)
    ic.fill(back, "#2e3a24", "#12180c", (200, 900), noise=0.3, chroma=0.12)
    for x in (300, 520, 610, 700, 800, 880, 960):
        w = rnd.uniform(18, 34)
        ic.fill(ic.intersect(back, ic.mask("rectangle", (x - w / 2, 200, x + w / 2, 900))), "#443c30", "#1a1610",
                (x - w / 2, x + w / 2), vertical=False, noise=0.2)

    def brush(dr):
        for _ in range(700):
            x, y = rnd.uniform(200, 1004), rnd.uniform(260, 900)
            r = rnd.uniform(5, 13)
            f = 0.45 + 0.45 * (y - 260) / 640
            col = (int(66 * f), int(86 * f), int(52 * f), 150) if rnd.random() < 0.6 else (12, 18, 10, 150)
            dr.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=col)

    ic.overlay(brush, back)
    for cx, cy, rx, ry, t in ((790, 326, 190, 84, 0.72), (600, 312, 160, 84, 0.78), (956, 360, 56, 66, 0.7), (478, 318, 70, 70, 0.74)):
        crown(ic, cx, cy, rx, ry, (scaled(WOOD[0], t), scaled(WOOD[1], t)), n=14, dabs=0.9)
    # understorey: low shrubs and fern fronds in the gap between the oak and the shelter
    for cx, cy, rx, ry in ((300, 800, 90, 70), (420, 830, 70, 56), (250, 700, 60, 60), (380, 640, 60, 70)):
        shrub(ic, cx, cy, rx, ry, 0.62)
    # pale birch at the edge of the wood, with its own small yellow-green crown
    bx = 372
    crown(ic, 404, 250, 84, 110, BIRCH, n=9, dabs=1.0)
    bt = [(bx - 22, 900), (bx - 16, 560), (bx - 9, 300), (bx + 9, 300), (bx + 17, 560), (bx + 24, 900)]
    ic.poly(bt, "#e0d8c4", "#847c6c", span=(bx - 24, bx + 24), vertical=False, noise=0.15, edge=4)
    ic.line([(bx - 1, 330), (bx + 30, 250)], 10, (196, 188, 170))
    ic.line([(bx - 4, 380), (bx - 40, 300)], 8, (196, 188, 170))
    for _ in range(18):  # black lenticels and bark patches
        y = rnd.uniform(320, 880)
        hw = 16 + (y - 300) / 600 * 6
        x0 = bx - hw + rnd.uniform(0, 4)
        ic.line([(x0, y), (x0 + rnd.uniform(10, hw * 1.4), y + rnd.uniform(-4, 4))], int(rnd.uniform(4, 9)), (36, 32, 28))
    ic.shade(ic.mask("rectangle", (bx + 4, 300, bx + 30, 900)), (20, 18, 14), 0.3, blur=4)
    crown(ic, 420, 200, 56, 64, (scaled(BIRCH[0], 1.12), BIRCH[1]), n=5, dabs=1.0)
    # fern layer rising to the trestle's knee in front of the understorey
    for x, b, sc in ((290, 900, 1.3), (420, 904, 1.2), (520, 900, 1.0)):
        fern(ic, x, b, sc, 0.8)
    # oak: gnarled trunk with a root flare, limbs, a rounded, lobed, domed crown over the trunk
    trunk = [(120, 904), (160, 870), (178, 800), (172, 700), (184, 600), (176, 470), (206, 420), (246, 440),
             (238, 560), (250, 690), (244, 800), (268, 872), (316, 906)]
    ic.poly(trunk, "#86725a", "#2e241a", span=(130, 290), vertical=False, noise=0.34, edge=4)
    tm = ic.poly_mask(trunk)
    for _ in range(9):  # bark fissures
        x = rnd.uniform(182, 244)
        ic.overlay(lambda d, x=x: d.line([(x, 440), (x + rnd.uniform(-10, 10), 640), (x + rnd.uniform(-14, 14), 880)],
                                         fill=(24, 18, 12, 150), width=int(rnd.uniform(4, 7))), tm)
    for _ in range(6):
        x, y = rnd.uniform(182, 214), rnd.uniform(460, 860)
        tint(ic, ic.mask("ellipse", (x - 10, y - 18, x + 10, y + 18)), tm, (170, 180, 120), 0.3, 3)
    ic.fill(ic.intersect(tm, ic.mask("ellipse", (196, 640, 222, 690))), "#1e1610", "#0c0806", noise=0.1)
    for p0, p1, w in (((196, 470), (90, 350), 30), ((230, 450), (330, 340), 28), ((212, 430), (214, 250), 24)):
        ic.line([p0, p1], w, (80, 64, 48))
        ic.line([(p0[0] - 4, p0[1]), (p1[0] - 4, p1[1])], max(4, w // 4), (150, 134, 110, 150))
    oak = blank()
    for cx, cy, rx, ry, n in ((106, 340, 104, 92, 9), (326, 336, 92, 86, 8), (214, 250, 132, 124, 12),
                              (150, 220, 80, 70, 6), (282, 214, 78, 66, 6)):
        oak = union(oak, crown(ic, cx, cy, rx, ry, LEAF, n=n, dabs=1.1))
    # dark gaps between the lobes, lit masses on the upper left of each
    for gx, gy in ((158, 360), (274, 356), (214, 330)):
        tint(ic, ic.mask("ellipse", (gx - 40, gy - 50, gx + 40, gy + 40)), oak, (8, 14, 4), 0.4, 14)
    for lx, ly, r in ((150, 170, 70), (70, 290, 56), (280, 180, 54)):
        tint(ic, ic.mask("ellipse", (lx - r, ly - r * 0.8, lx + r, ly + r * 0.8)), oak, (214, 226, 130), 0.22, 16)
    ic.shade(ic.mask("rectangle", (160, 440, 260, 560)), (10, 8, 4), 0.35, blur=16)


def shelter(ic: Icon) -> None:
    """Open drying shelter: forked posts, bark lean-to, a pole hung with bunches."""
    for x, lean in ((500, -8), (730, 0), (960, 8)):
        pole(ic, (x + lean, 920), (x, 440), 26)
        ic.line([(x, 452), (x - 22, 410)], 16, (86, 70, 52))
        ic.line([(x, 452), (x + 20, 414)], 16, (86, 70, 52))
    roof = [(470, 300), (1004, 294), (1016, 452), (452, 460)]
    bark_roof(ic, roof)
    ic.shade(ic.mask("rectangle", (470, 460, 1000, 540)), alpha=0.45, blur=16)
    pole(ic, (452, 482), (1012, 476), 22)
    kinds = [(LAVENDER, 104, 250), (SAGE, 110, 226), (None, 0, 170), (TANSY, 112, 244), (POPPY, 100, 218)]
    xs = [548, 660, 752, 838, 944]
    for x, (kind, w, h) in zip(xs, kinds):
        if kind is None:
            root_string(ic, (x, 494), h)
        else:
            bunch(ic, (x + ic.random.uniform(-6, 6), 494), w, h * ic.random.uniform(0.94, 1.04), kind)
    # the roof overhang throws a deep shadow over the tops of the hanging bunches
    ic.shade(ic.mask("rectangle", (452, 450, 1016, 600)), (10, 8, 4), 0.55, blur=26)


def ground(ic: Icon) -> None:
    rnd = ic.random
    top = [(14, 880)] + [(x, 872 + rnd.uniform(-10, 8)) for x in np.linspace(80, 960, 10)] + [(1012, 880)]
    pts = top + [(1014, 1000), (16, 1000)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#6a7a3c", "#3e4a22", (870, 1000), noise=0.32, chroma=0.12)

    def grass(dr):
        for _ in range(520):
            x, y = rnd.uniform(14, 1012), rnd.uniform(866, 998)
            a = rnd.uniform(-2.4, -0.7)
            L = rnd.uniform(10, 22)
            col = (170, 176, 100, 150) if rnd.random() < 0.5 else (40, 50, 22, 150)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(grass)
    flowers(ic, None, (30, 880, 1000, 990), 46)
    ic.shade(ic.mask("rectangle", (14, 866, 480, 930)), (10, 16, 6), 0.3, blur=18)


def table(ic: Icon) -> None:
    """Low sorting trestle with bark strips and roots."""
    T = 858
    ic.shade(ic.mask("ellipse", (540, 950, 850, 990)), alpha=0.4, blur=8, clip=False)
    for x in (570, 810):
        timber(ic, (x - 20, 970), (x + 14, T), 14, "#86603e", "#4a3220")
        timber(ic, (x + 20, 970), (x - 14, T), 14, "#86603e", "#4a3220")
    top = [(540, T - 24), (844, T - 26), (852, T + 6), (534, T + 8)]
    ic.poly(top, "#a88258", "#6a4c30", edge=4)
    for x, L, d in ((560, 90, -6), (640, 80, 4), (700, 96, -3)):
        bark_strip(ic, x, T - 24, L, d)
    root(ic, (760, T - 20), (830, T - 30), 12)
    root(ic, (748, T - 8), (820, T - 4), 10)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.64
    ic.grade["mute"] = 0.88

    woods(ic)
    shelter(ic)
    ground(ic)
    for x, b, sc in ((60, 904, 1.0), (340, 904, 0.9)):
        fern(ic, x, b, sc, 0.95)
    table(ic)
    basket_of(ic, 330, 910, 500, 992, (MINT, SAGE, YARROW))
    basket_of(ic, 868, 916, 1012, 994, (LAVENDER, TANSY, POPPY))
