"""Vineyard Estate (vineyard_estate): trellised vine rows on a hillside hung with dark grapes, a stone
press house with a tile roof and a cellar door, casks of young wine in front.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/vineyard_estate/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/vineyard_estate

Identity: the slope. Rows of vines on stakes and wires climb a warm earth hillside rising to the left,
each row a band of vine leaves with purple grape clusters hanging below; on the lower right a
rubble-stone press house under a terracotta roof with an arched cellar door, a pyramid of casks
lying end-on beside it and a tub of picked grapes at the front. Vanilla winery is a goblet and a
bunch; this is the estate that makes it.

Local helpers: the orchard-family helpers of ``nursery_orchard`` (``crown``, ``leaf_dabs``,
``fruit``, ``shingles``, ``timber``, ``tint``) plus ``stones`` and ``cask_end`` (from
victualling_yard), ``cluster`` (bunch of grapes), ``vine_row`` (trellised row of vines in
perspective) and ``hillside``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
REFS = ("winery", "fruit_orchard", "farming_village", "terraces")

LEAF = ("#6e9434", "#1a2e0c")
GRAPE = ((66, 28, 52), (110, 70, 98), (24, 8, 20))
GRAPE2 = ((84, 32, 56), (130, 80, 104), (34, 10, 24))
GRAPE3 = ((50, 28, 54), (90, 66, 98), (18, 8, 18))
TILE = ("#b8704a", "#62301c")


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
            x, y = cx + math.cos(a) * rx * 0.86, cy + math.sin(a) * ry * 0.86
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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
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
    paste_clipped(ic, lay, m)


def cask_end(ic: Icon, cx, cy, r, depth: float = 0.32, tone: float = 1.0) -> None:
    """Cask lying on its side, seen end-on from the raised camera: chime ring, iron hoop, boards, bung."""
    k = lambda c: tuple(int(v * tone) for v in c)  # noqa: E731
    d = r * depth
    body = union(ic.mask("ellipse", (cx - r * 0.98, cy - r * 0.98 - d, cx + r * 0.98, cy + r * 0.98 - d)),
                 ic.mask("rectangle", (cx - r * 0.98, cy - d, cx + r * 0.98, cy)))
    ic.fill(body, k((160, 110, 64)), k((66, 40, 22)), radial=(cx - r * 0.4, cy - r - d, r * 2.2), noise=0.16)
    for f in (0.35, 0.8):
        y = cy - d * f
        ic.overlay(lambda dd, y=y: dd.arc((cx - r * 0.98, y - r * 0.98, cx + r * 0.98, y + r * 0.98), 190, 350,
                                          fill=(52, 48, 46, 230), width=8), body)
    ring = ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    ic.fill(ring, k((104, 66, 38)), k((40, 24, 12)), radial=(cx - r * 0.5, cy - r * 0.6, r * 2), noise=0.14)
    ic.overlay(lambda dd: dd.ellipse((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), outline=(56, 54, 54, 255),
                                     width=max(5, int(r * 0.1))))
    hr = r * 0.8
    head = ic.mask("ellipse", (cx - hr, cy - hr, cx + hr, cy + hr))
    ic.fill(head, k((188, 132, 80)), k((84, 52, 28)), radial=(cx - hr * 0.55, cy - hr * 0.65, hr * 1.9), noise=0.16)
    ic.overlay(lambda dd: [dd.line([(cx + f * hr, cy - hr), (cx + f * hr, cy + hr)], fill=(60, 38, 20, 90), width=3)
                           for f in (-0.45, 0.05, 0.5)], head)
    tint(ic, ic.mask("ellipse", (cx - hr * 0.2, cy - hr * 0.1, cx + hr * 1.5, cy + hr * 1.5)), head, (20, 10, 4), 0.4, 10)
    ic.draw.ellipse((cx - r * 0.1, cy + r * 0.25, cx + r * 0.1, cy + r * 0.43), fill=(46, 30, 18, 255))
    # wine stain below the bung
    tint(ic, ic.mask("ellipse", (cx - r * 0.12, cy + r * 0.4, cx + r * 0.1, cy + r * 0.75)), head, (70, 10, 30), 0.35, 3)


def cluster(ic: Icon, x, y, r, n: int = 9) -> list:
    """Bunch of grapes hanging from (x, y): berries in an inverted triangle. Returns fruit items."""
    rnd = ic.random
    items = []
    rows = rnd.choice(([3, 3, 2, 1], [2, 3, 2, 1], [3, 2, 2, 1, 1], [2, 3, 3, 2, 1])) if n >= 8 else         rnd.choice(([2, 2, 1], [3, 2, 1], [2, 2, 1, 1]))
    r *= rnd.uniform(0.85, 1.12)
    lean = rnd.uniform(-0.25, 0.25)
    yy = y + r
    for k, cnt in enumerate(rows):
        for j in range(cnt):
            xx = x + (j - (cnt - 1) / 2) * r * 1.5 + rnd.uniform(-3, 3) + lean * (yy - y)
            items.append((xx, yy + rnd.uniform(-2, 2), r * rnd.uniform(0.92, 1.08),
                          rnd.choice((GRAPE, GRAPE, GRAPE2, GRAPE3))))
        yy += r * 1.25
    return items


def vine_row(ic: Icon, x0, y0, x1, y1, s: float, tone: float = 1.0) -> None:
    """Trellised row of vines along the line (x0, y0)-(x1, y1) (the ground line): stakes and a wire,
    gnarled trunks, a leafy band on the wire, bunches of grapes hanging under the leaves."""
    rnd = ic.random
    band = 70 * s
    L = math.hypot(x1 - x0, y1 - y0)

    def at(t, lift=0.0):
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - lift

    # the row's shadow on the slope below it and a trodden strip
    tint(ic, ic.poly_mask([at(0, -4), at(1, -4), at(1, -40 * s), at(0, -40 * s)]), None, (30, 20, 10), 0.35, 10)
    # stakes and wire
    n_st = max(3, int(L / (150 * s)))
    for k in range(n_st + 1):
        t = k / n_st
        px, py = at(t)
        ic.rect((px - 6 * s, py - band * 1.55, px + 6 * s, py + 4), "#a88c66", "#5a4630", vertical=False, edge=3)
    ic.line([at(0, band * 1.05), at(1, band * 1.05)], max(3, int(4 * s)), (60, 56, 50, 200))
    # gnarled trunks
    n_v = max(4, int(L / (70 * s)))
    for k in range(n_v):
        t = (k + 0.5) / n_v + rnd.uniform(-0.02, 0.02)
        px, py = at(t)
        ic.line([(px, py + 2), (px + rnd.uniform(-6, 6) * s, py - band * 0.5), (px + rnd.uniform(-10, 10) * s, py - band)],
                int(12 * s), (82, 60, 44))
        ic.line([(px - 3 * s, py), (px - 3 * s, py - band * 0.8)], int(4 * s), (150, 120, 96, 130))
    # leafy band on the wire: blobs along the row
    m = blank()
    cols = (scaled(LEAF[0], tone), scaled(LEAF[1], tone))
    nb = max(5, int(L / (46 * s)))
    for k in range(nb + 1):
        t = k / nb
        px, py = at(t, band * 1.2)
        br = rnd.uniform(28, 50) * s
        bm = ic.poly_mask(ic.jitter(px + rnd.uniform(-10, 10), py + rnd.uniform(-20, 10) * s, br * 1.1, br * 0.9, 18, 0.18))
        ic.fill(bm, cols[0], cols[1], radial=(px - br * 0.7, py - br, br * 2.4), noise=0.28, chroma=0.12)
        m = union(m, bm)
    xs = [x0, x1]
    ys = [y0 - band * 1.2, y1 - band * 1.2]
    cx, cy = (x0 + x1) / 2, (ys[0] + ys[1]) / 2
    leaf_dabs(ic, cx, cy, abs(x1 - x0) / 2 + 40, abs(ys[1] - ys[0]) / 2 + 50 * s, m, int(L * s * 1.1), cols)
    tint(ic, ic.poly_mask([at(0, band * 1.2), at(1, band * 1.2), at(1, band * 0.4), at(0, band * 0.4)]), m,
         (10, 18, 6), 0.35, 10)
    # young shoots curling up out of the leaves
    for _ in range(int(L / (60 * s))):
        px, py = at(rnd.uniform(0.02, 0.98), band * 1.5)
        ic.line([(px, py + 10 * s), (px + rnd.uniform(-10, 10) * s, py - 16 * s), (px + rnd.uniform(-20, 20) * s, py - 30 * s)],
                max(3, int(5 * s)), (110, 130, 60))
    # bunches hanging below the leaves
    items = []
    nc = max(3, int(L / (80 * s)))
    for k in range(nc):
        if rnd.random() < 0.2:
            continue
        t = (k + 0.15 + rnd.uniform(0, 0.7)) / nc
        px, py = at(t, band * 0.78)
        items += cluster(ic, px, py, 10.5 * s, 9 if s > 0.8 else 6)
    fruit(ic, items)


def hillside(ic: Icon, top) -> Image.Image:
    """Warm earth slope with dry grass and stones; ``top`` is the skyline of the hill."""
    rnd = ic.random
    pts = top + [(top[-1][0], 1000), (16, 1000)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#8a6c46", "#4a3822", (min(p[1] for p in top), 1000), noise=0.34, chroma=0.12)

    def grass(dr):
        for _ in range(500):
            x, y = rnd.uniform(16, top[-1][0]), rnd.uniform(200, 1000)
            a = rnd.uniform(-2.4, -0.7)
            L = rnd.uniform(8, 18)
            col = (200, 180, 120, 110) if rnd.random() < 0.5 else (60, 48, 30, 120)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(grass, m)
    # a lit grassy crest along the skyline
    crest = [(x, y) for x, y in top] + [(x, y + 30) for x, y in top[::-1]]
    tint(ic, ic.poly_mask(crest), m, (150, 150, 70), 0.3, 8)
    ic.outline(pts, 4, (40, 30, 16, 150))
    return m


# ---------------------------------------------------------------- parts
def press_house(ic: Icon) -> None:
    rnd = ic.random
    X0, X1, WT, WB = 590, 1004, 560, 900
    wm = ic.mask("rectangle", (X0, WT, X1, WB))
    stones(ic, (X0, WT, X1, WB), "#b2a48a", "#7a6c58", course=34, clip=wm)
    tint(ic, ic.mask("rectangle", (X0, WB - 80, X1, WB + 10)), wm, (50, 50, 24), 0.35, 16)
    ic.outline([(X0, WT), (X1, WT), (X1, WB), (X0, WB)], 4, (40, 26, 16, 170))
    # arched cellar door: dark vault, open leaf
    ic.door(632, 690, 752, WB, arched=True, surround="#c8bca2")
    vault = union(ic.mask("ellipse", (640, 698, 744, 802)), ic.mask("rectangle", (640, 750, 744, WB)))
    ic.fill(vault, "#241a14", "#0e0a08", (698, WB), noise=0.1)
    cask_end(ic, 692, 858, 34, tone=0.55)  # a cask in the dark cellar mouth
    ic.window(840, 630, 880, 680)
    # terracotta roof with a small loading hoist beam
    roof = [(640, 360), (952, 352), (1020, 580), (568, 588)]
    rm = shingles(ic, roof, TILE[0], TILE[1], course=30, stagger=40)
    for _ in range(14):
        x, y = rnd.uniform(600, 1000), rnd.uniform(370, 570)
        r = rnd.uniform(10, 24)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), rm,
             (206, 196, 140) if rnd.random() < 0.5 else (40, 30, 20), 0.16, 4)
    ic.shade(ic.mask("rectangle", (X0, WT, X1, WT + 60)), alpha=0.5, blur=14)
    ic.line([(640, 360), (952, 352)], 18, (150, 84, 56))


def casks(ic: Icon) -> None:
    ic.shade(ic.mask("ellipse", (770, 950, 1020, 1004)), alpha=0.5, blur=10, clip=False)
    for cx, cy, r in ((826, 930, 58), (946, 930, 58), (886, 832, 56)):
        cask_end(ic, cx, cy, r)


def tub(ic: Icon) -> None:
    """Shallow wooden tub heaped with picked bunches."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (470, 964, 690, 1004)), alpha=0.45, blur=8, clip=False)
    ic.fill(ic.mask("ellipse", (480, 880, 680, 924)), "#2a1420", "#140a10")
    items = []
    for _ in range(4):
        items += cluster(ic, rnd.uniform(510, 640), rnd.uniform(846, 868), 13, 9)
    fruit(ic, items)
    for _ in range(5):
        a = rnd.uniform(-2.8, -0.4)
        px, py = rnd.uniform(500, 660), 880
        ic.fill(ic.poly_mask([(px, py), (px + math.cos(a) * 20 - 10, py + math.sin(a) * 20),
                              (px + math.cos(a) * 40, py + math.sin(a) * 40),
                              (px + math.cos(a) * 20 + 10, py + math.sin(a) * 20 + 6)]), LEAF[0], LEAF[1],
                radial=(px - 10, py - 30, 50), noise=0.2)
    body = [(478, 902), (682, 902), (668, 990), (492, 990)]
    ic.poly(body, "#9a7048", "#4e3420", edge=4)
    for f in (0.3, 0.75):
        y = 902 + 88 * f
        ic.line([(478 + 14 * f, y), (682 - 14 * f, y)], 9, (56, 52, 50))
    ic.fill(ic.mask("ellipse", (476, 890, 684, 916)), "#b48e62", "#7e5e3c", noise=0.14)
    ic.fill(ic.mask("ellipse", (488, 894, 672, 912)), "#3a1a2a", "#1a0a12", noise=0.1)
    items = []
    for _ in range(3):
        items += cluster(ic, rnd.uniform(520, 640), rnd.uniform(872, 884), 12, 9)
    fruit(ic, items)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.88

    top = [(16, 250), (120, 262), (240, 300), (360, 356), (480, 424), (600, 500), (700, 560)]
    hillside(ic, top)
    press_house(ic)
    # rows climbing the slope, back (high) to front (low)
    rows = [((36, 300), (470, 454), 0.5, 0.74),
            ((30, 420), (560, 612), 0.62, 0.8),
            ((24, 560), (600, 720), 0.76, 0.88),
            ((20, 718), (620, 840), 0.9, 0.95),
            ((16, 900), (560, 972), 1.08, 1.0)]
    for (x0, y0), (x1, y1), s, tone in rows:
        vine_row(ic, x0, y0, x1, y1, s, tone)
    casks(ic)
    tub(ic)
