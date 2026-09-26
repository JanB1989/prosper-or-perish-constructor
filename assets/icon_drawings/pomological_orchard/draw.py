"""Grafted Orchard (pomological_orchard): neat rows of pruned grafted fruit trees heavy with apples
and pears, a brick garden wall and a brick orchard house with a pear trained flat on its front.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pomological_orchard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pomological_orchard

Identity (tier 2 of the fruit orchard chain, after the Nursery Orchard): the nursery's saplings
have grown into a managed orchard. Two rows of equal, open-centre pruned trees with limewashed
trunks, laden with red apples and yellow pears, stand on mown grass before a coped brick garden
wall; on the right a brick orchard house under a tile roof carries an espaliered pear. An orchard
ladder leans into the crown of the right-hand tree; a crate and a basket of picked fruit in front.
More structure than the nursery: brick and tile instead of boards, trained grown trees instead of
staked whips.

Local helpers: the orchard-family helpers of ``nursery_orchard`` (``crown``, ``leaf_dabs``,
``fruit``, ``shingles``, ``planks``, ``timber``, ``tint``) plus ``bricks`` (from victualling_yard),
``crate`` (open crate), ``goblet_tree`` (pruned open-centre fruit tree), ``espalier`` (wall-trained
pear) and ``ladder``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 37
REFS = ("fruit_orchard", "farming_village", "royal_garden", "forest_village")

LEAF = ("#6e9638", "#1a300c")
APPLE = ((142, 34, 18), (184, 76, 44), (66, 20, 10))
APPLE2 = ((176, 72, 34), (214, 140, 76), (86, 30, 12))
BLUSH = ((168, 96, 40), (206, 150, 76), (84, 36, 14))
YGREEN = ((150, 150, 58), (196, 190, 104), (76, 70, 24))


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


BRICK = ("#b0704e", "#6a3c28")
TILE = ("#b06a48", "#62301c")
LIME = "#c8bea8"
PEAR = ((160, 156, 56), (206, 198, 110), (80, 76, 22))


def bricks(ic: Icon, m: Image.Image, box, base=BRICK[0], dark=BRICK[1], course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:
                col = (40, 22, 18, 90)
            else:
                col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    paste_clipped(ic, lay, m)


def crate(ic: Icon, x0, y0, x1, y1, c=("#8e6a46", "#4e3420")) -> None:
    """Open slatted crate: boarded front with corner battens, darker right end."""
    front = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    m = ic.poly_mask(front)
    ic.fill(m, c[0], c[1], (y0, y1), noise=0.2)
    ic.overlay(lambda d: [d.line([(x0, y), (x1, y + ic.random.uniform(-2, 2))], fill=(40, 24, 12, 140), width=4)
                          for y in np.linspace(y0, y1, 4)[1:-1]], m)
    for bx in (x0 + 10, x1 - 10):
        timber(ic, (bx, y0 + 2), (bx, y1 - 2), 16, "#8a6440", "#4e3522")
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.3, y0, x1 + 20, y1)), m, (0, 0, 0), 0.25, 10)
    ic.outline(front, 4, (40, 26, 16, 170))


def orchard_fruit(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Shaded apples (x, y, r, palette): red-brown underside, body, soft lit side, small warm glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in sorted(items, key=lambda it: it[1]):
            dr.ellipse((x - r, y - r * 0.95, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r + 1.5, y - r * 0.95 + 1, x + r - 2, y + r * 0.55), fill=mid + (255,))
            dr.ellipse((x - r * 0.75, y - r * 0.8, x + r * 0.05, y - r * 0.05), fill=lit + (190,))
            g = max(r * 0.16, 1.6)
            gx, gy = x - r * 0.4, y - r * 0.45
            dr.ellipse((gx - g, gy - g, gx + g, gy + g), fill=(246, 222, 180, 170))
            dr.line([(x + 1, y - r * 0.9), (x + 3, y - r * 1.25)], fill=(60, 40, 20, 200), width=2)

    ic.overlay(paint, clip)


def goblet_tree(ic: Icon, x, base, h, tone: float = 1.0, apples: int = 14, pears: float = 0.0) -> Image.Image:
    """Grafted open-centre tree: short trunk limewashed on its lower half, scaffold limbs in a wide V,
    a broad flat goblet crown of lobes with a broken top and clustered fruit on the lower, outer
    crown. Returns the crown mask."""
    rnd = ic.random
    top = base - h
    rx, ry = h * 0.265, h * 0.215
    cy = top + ry + h * 0.03
    fork = base - h * 0.3
    trunk = [(x - h * 0.036, base + 4), (x - h * 0.03, fork), (x + h * 0.03, fork), (x + h * 0.042, base + 4)]
    tm = ic.poly_mask(trunk)
    ic.fill(tm, "#8a7258", "#3e2e20", (x - h * 0.04, x + h * 0.04), vertical=False, noise=0.26)
    wash = ic.intersect(tm, ic.mask("rectangle", (0, base - h * 0.17, SIZE, base + 10)))
    ic.fill(wash, LIME, "#7e7466", (x - h * 0.04, x + h * 0.045), vertical=False, noise=0.16)
    tint(ic, ic.mask("rectangle", (x + h * 0.008, base - h * 0.2, x + h * 0.06, base + 10)), tm, (30, 22, 14), 0.35, 3)
    ic.line([(x - h * 0.036, base - h * 0.17), (x + h * 0.034, base - h * 0.172)], 3, (90, 76, 60, 160))
    ic.outline(trunk, 4, (40, 28, 16, 170))
    # scaffold limbs: wide open V, the centre left open
    limbs = []
    for dx, dy in ((-rx * 0.82, ry * 0.25), (-rx * 0.3, -ry * 0.35), (rx * 0.34, -ry * 0.3), (rx * 0.85, ry * 0.2)):
        dx *= rnd.uniform(0.9, 1.08)
        pts = [(x, fork + 8), (x + dx * 0.35, fork - h * 0.1), (x + dx, cy + dy)]
        limbs.append(pts)
        ic.line(pts, int(h * 0.032), (78, 60, 44))
        ic.line([(px - 3, py) for px, py in pts], int(h * 0.011), (156, 130, 104, 150))
    cols = (scaled(LEAF[0], tone), scaled(LEAF[1], tone))
    # crown lobes: two broad outer masses, a lower back mass and one or two smaller top tufts
    m = blank()
    lobes = [(x - rx * 0.05, cy + ry * 0.05, rx * 0.8, ry * 0.8, 8),
             (x - rx * 0.55, cy + ry * 0.2, rx * 0.48, ry * 0.8, 7),
             (x + rx * 0.55, cy + ry * 0.1, rx * 0.47, ry * 0.86, 7),
             (x - rx * 0.18 + rnd.uniform(-8, 8), cy - ry * 0.62, rx * 0.3, ry * 0.5, 5)]
    if rnd.random() < 0.7:
        lobes.append((x + rx * 0.3 + rnd.uniform(-8, 8), cy - ry * 0.5, rx * 0.26, ry * 0.46, 4))
    for lx, ly, lrx, lry, n in lobes:
        m = union(m, crown(ic, lx, ly, lrx, lry, cols, n=n, dabs=0.9))
    # open centre: shade the heart of the crown and let the scaffold limbs show through
    heart = ic.mask("ellipse", (x - rx * 0.32, cy - ry * 0.1, x + rx * 0.32, cy + ry * 0.9))
    tint(ic, heart, m, (8, 14, 4), 0.45, 12)
    for pts in limbs:
        ic.line([pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * 0.7, pts[1][1] + (pts[2][1] - pts[1][1]) * 0.7)],
                int(h * 0.022), (70, 52, 36, 210))
    # fruit in clusters of 2-4 on the lower and outer crown, some half hidden by leaves
    items = []
    while len(items) < apples:
        side = rnd.choice((-1, 1))
        a = rnd.uniform(-0.15, 1.1) if side > 0 else math.pi - rnd.uniform(-0.15, 1.1)
        rr = rnd.uniform(0.62, 0.92)
        ccx, ccy = x + math.cos(a) * rx * rr, cy + ry * 0.12 + math.sin(a) * ry * 0.8 * rr
        k = rnd.randint(2, 4)
        pal0 = PEAR if rnd.random() < pears else None
        for _ in range(k):
            r = h * rnd.uniform(0.022, 0.032)
            pal = pal0 or rnd.choice((APPLE, APPLE, APPLE, BLUSH, BLUSH, YGREEN))
            items.append((ccx + rnd.uniform(-1.6, 1.6) * r, ccy + rnd.uniform(-0.8, 1.2) * r, r, pal))
    orchard_fruit(ic, items, m)
    leaf_dabs(ic, x, cy + ry * 0.35, rx * 0.95, ry * 0.7, m, int(rx * ry / 260), cols)
    ic.shade(ic.mask("ellipse", (x - rx * 0.7, base - 16, x + rx * 0.9, base + 22)), alpha=0.4, blur=10, clip=False)
    return m


def espalier(ic: Icon, x, base, tiers) -> None:
    """Pear trained flat on the wall: an upright stem and clear horizontal branch tiers
    (y, x_left, x_right), green leaf dots along them and a few pears hanging below."""
    rnd = ic.random
    top = min(t[0] for t in tiers) - 16
    ic.line([(x, base), (x - 2, top)], 14, (52, 36, 24))
    ic.line([(x - 5, base), (x - 7, top)], 4, (130, 104, 76, 150))
    leaves, items = [], []
    for y, xl, xr in tiers:
        for end in (xl, xr):
            if abs(end - x) < 20:
                continue
            sgn = 1 if end > x else -1
            pts = [(x, y + 16), (x + sgn * 18, y), (end, y + rnd.uniform(-3, 3))]
            ic.line(pts, 12, (50, 34, 22))
            ic.line([(px, py - 3) for px, py in pts[1:]], 3, (140, 110, 80, 150))
            for px in np.arange(min(x, end) + 14, max(x, end), 16):
                leaves.append((px + rnd.uniform(-4, 4), y + rnd.uniform(-14, -4)))
                if rnd.random() < 0.6:
                    leaves.append((px + rnd.uniform(-4, 4), y + rnd.uniform(4, 12)))
                if rnd.random() < 0.12:
                    items.append((px, y + 22, rnd.uniform(9, 11), PEAR))

    def dots(dr):
        for lx, ly in leaves:
            r = rnd.uniform(8, 11)
            lit = rnd.random() < 0.45
            dr.ellipse((lx - r, ly - r * 0.75, lx + r, ly + r * 0.75), fill=(34, 56, 18, 255))
            col = (132, 164, 70, 255) if lit else (84, 118, 44, 255)
            dr.ellipse((lx - r + 2, ly - r * 0.75 + 1, lx + r - 3, ly + r * 0.4), fill=col)

    ic.overlay(dots)
    for fx, fy, r, pal in items:
        ic.fill(ic.mask("ellipse", (fx - r * 0.7, fy - r * 1.6, fx + r * 0.7, fy)), pal[0], pal[2],
                radial=(fx - r * 0.5, fy - r * 1.5, r * 2), noise=0.1)
    orchard_fruit(ic, [(fx, fy + r * 0.3, r, pal) for fx, fy, r, pal in items])


def ladder(ic: Icon, foot, top, w: float = 60) -> None:
    """Tapering orchard ladder: two rails and rungs, lit left rail."""
    (x0, y0), (x1, y1) = foot, top
    l0, r0 = (x0 - w / 2, y0), (x0 + w / 2, y0)
    l1, r1 = (x1 - w * 0.25, y1), (x1 + w * 0.25, y1)
    for t in np.linspace(0.08, 0.95, 7):
        a = (l0[0] + (l1[0] - l0[0]) * t, l0[1] + (l1[1] - l0[1]) * t)
        b = (r0[0] + (r1[0] - r0[0]) * t, r0[1] + (r1[1] - r0[1]) * t)
        timber(ic, a, b, 10, "#b08a60", "#6a4c30")
    timber(ic, l0, l1, 14, "#bc9a70", "#6a4c30")
    timber(ic, r0, r1, 14, "#9a7650", "#5a3e26")


# ---------------------------------------------------------------- parts
def house(ic: Icon) -> None:
    rnd = ic.random
    X0, X1, WT, WB = 646, 1000, 560, 884
    wm = ic.mask("rectangle", (X0, WT, X1, WB))
    bricks(ic, wm, (X0, WT, X1, WB))
    tint(ic, ic.mask("rectangle", (X0, WB - 80, X1, WB + 10)), wm, (40, 44, 20), 0.35, 16)
    ic.outline([(X0, WT), (X1, WT), (X1, WB), (X0, WB)], 4, (40, 26, 16, 170))
    ic.door(902, 700, 972, WB, arched=False, surround="#b8ab94")
    ic.window(700, 640, 760, 700)
    espalier(ic, 836, WB, ((652, 784, 890), (736, 664, 890), (812, 664, 890)))
    roof = [(700, 330), (946, 324), (1018, 580), (626, 586)]
    rm = shingles(ic, roof, TILE[0], TILE[1], course=30, stagger=40)
    for _ in range(14):
        x, y = rnd.uniform(660, 1000), rnd.uniform(350, 570)
        r = rnd.uniform(10, 24)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), rm,
             (206, 196, 140) if rnd.random() < 0.5 else (40, 30, 20), 0.16, 4)
    ic.shade(ic.mask("rectangle", (X0, WT, X1, WT + 60)), alpha=0.5, blur=14)
    ic.line([(700, 330), (946, 324)], 18, (140, 76, 50))
    ic.rect((890, 270, 930, 360), "#9a5e46", "#5c3628", vertical=False, edge=4)
    ic.rect((884, 262, 936, 280), "#b8ab94", "#8a7e6a", edge=4)


def wall(ic: Icon) -> None:
    X0, X1, T, B = 16, 660, 604, 800
    wm = ic.mask("rectangle", (X0, T, X1, B))
    bricks(ic, wm, (X0, T, X1, B), "#6e5c52", "#3e322c")
    tint(ic, ic.mask("rectangle", (X0, B - 60, X1, B + 10)), wm, (30, 40, 16), 0.35, 16)
    tint(ic, ic.mask("rectangle", (X1 - 60, T, X1 + 10, B)), wm, (10, 6, 4), 0.35, 14)  # shade by the house
    ic.outline([(X0, T), (X1, T), (X1, B), (X0, B)], 4, (40, 26, 16, 170))
    cop = [(X0 - 6, T - 16), (X1 + 2, T - 16), (X1 + 2, T + 6), (X0 - 6, T + 6)]
    ic.poly(cop, "#9a9282", "#5e584c", edge=4)
    ic.line([(X0 - 4, T - 13), (X1, T - 13)], 5, (214, 206, 186))
    ic.shade(ic.mask("rectangle", (X0, T + 6, X1, T + 22)), alpha=0.5, blur=5)


def ground(ic: Icon) -> None:
    rnd = ic.random
    pts = [(14, 780), (1012, 780), (1014, 1000), (16, 1000)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#5e6a34", "#3a4420", (780, 1000), noise=0.3, chroma=0.1)

    def grass(dr):
        for _ in range(520):
            x, y = rnd.uniform(14, 1012), rnd.uniform(784, 998)
            a = rnd.uniform(-2.4, -0.7)
            L = rnd.uniform(8, 18)
            col = (176, 180, 104, 140) if rnd.random() < 0.5 else (44, 52, 22, 140)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(grass, m)
    # mowing bands of alternating value, edges slightly wavy
    for y0, y1, col, a in ((782, 846, (214, 220, 150), 0.14), (846, 916, (16, 24, 6), 0.22), (916, 1000, (214, 220, 150), 0.1)):
        band = ic.poly_mask([(0, y0 + rnd.uniform(-5, 5))] + [(x, y0 + rnd.uniform(-6, 6)) for x in np.linspace(120, 900, 6)]
                            + [(SIZE, y0 + rnd.uniform(-5, 5)), (SIZE, y1), (0, y1)])
        tint(ic, band, m, col, a, 6)
    ic.outline(pts, 4, (40, 30, 16, 150))
    orchard_fruit(ic, [(250, 972, 12, APPLE), (470, 986, 11, BLUSH)])


def tufts(ic: Icon, x, base, s: float) -> None:
    """Darker unmown grass tufts round a tree base."""
    rnd = ic.random

    def paint(dr):
        for _ in range(int(26 * s)):
            gx = x + rnd.uniform(-44, 48) * s
            gy = base + rnd.uniform(-2, 12) * s
            for _ in range(3):
                a = rnd.uniform(-2.5, -0.6)
                L = rnd.uniform(10, 22) * s
                col = (30, 40, 14, 220) if rnd.random() < 0.7 else (120, 130, 64, 200)
                dr.line([(gx, gy), (gx + math.cos(a) * L, gy + math.sin(a) * L)], fill=col, width=4)

    ic.overlay(paint)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.9

    wall(ic)
    house(ic)
    ground(ic)
    for x in (262, 504):  # back row, smaller, darker and in the wall's shade
        goblet_tree(ic, x, 830, 380, tone=0.7, apples=7)
        tufts(ic, x, 830, 0.8)
    for x, p in ((140, 0.0), (384, 0.3), (626, 0.0)):  # front row, neat and equal
        goblet_tree(ic, x, 960, 470, apples=16, pears=p)
        tufts(ic, x, 960, 1.0)
    ladder(ic, (640, 986), (600, 640))
    # crate and basket of picked fruit
    ic.shade(ic.mask("ellipse", (700, 960, 930, 1004)), alpha=0.45, blur=8, clip=False)
    ic.fill(ic.mask("rectangle", (720, 884, 900, 910)), "#3a2412", "#20140a")
    heap = [(rnd.uniform(730, 890), rnd.uniform(880, 904), rnd.uniform(15, 17), rnd.choice((APPLE, APPLE, BLUSH, YGREEN, PEAR)))
            for _ in range(22)]
    orchard_fruit(ic, heap)
    crate(ic, 716, 900, 904, 984)
    ic.shade(ic.mask("ellipse", (900, 968, 1018, 1004)), alpha=0.45, blur=8, clip=False)
    ic.fill(ic.mask("ellipse", (916, 904, 1004, 928)), "#3a2412", "#20140a")
    fruit(ic, [(rnd.uniform(924, 996), rnd.uniform(902, 920), rnd.uniform(14, 16), PEAR) for _ in range(9)])
    ic.basket(912, 914, 1008, 994)
