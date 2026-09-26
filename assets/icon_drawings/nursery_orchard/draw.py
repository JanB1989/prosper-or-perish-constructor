"""Nursery Orchard (nursery_orchard): rows of young staked fruit saplings beside a board potting shed.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/nursery_orchard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/nursery_orchard

Identity (tier 1 of the fruit orchard chain, after vanilla fruit_orchard): no grown tree yet, but a
nursery. Three raked beds of young grafted saplings, each tied to a pale stake with a waxed graft
band low on the stem, a wattle hurdle behind them; on the right a small board potting shed under a
wooden-shingle roof with a potting bench of clay pots and seedlings, a stack of pots and a basket of
the old orchard's apples in front.

Local helpers: ``union``, ``tint``, ``paste_clipped``, ``scaled``, ``shingles``, ``planks``,
``timber`` (food-family finish), plus orchard-family ``crown`` (leafy blob crown with leaf dabs and a
shaded underside), ``fruit`` (round shaded fruit), ``stake``, ``sapling``, ``soil`` (raked bed),
``wattle`` (woven hurdle), ``pot`` (terracotta flowerpot).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("fruit_orchard", "farming_village", "forest_village", "royal_garden")

LEAF = ("#7a9c46", "#223612")
YOUNG = ("#6e9c34", "#16300a")
APPLE = ((170, 40, 28), (218, 96, 64), (80, 16, 10))
APPLE2 = ((186, 72, 34), (226, 146, 76), (92, 30, 12))
GOLD = ((190, 150, 52), (230, 200, 110), (100, 70, 20))
CLAY = ("#b86c46", "#5a2c16")
STAKE = ("#a08662", "#56442e")


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


def stake(ic: Icon, x, top, base, w: float = 16) -> None:
    """Split-wood stake: pale lit left face, darker right face, cut top."""
    pts = [(x - w / 2, base), (x - w / 2 + 1, top + 6), (x, top), (x + w / 2, top + 4), (x + w / 2, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, STAKE[0], STAKE[1], (x - w / 2, x + w / 2), vertical=False, noise=0.2)
    tint(ic, ic.mask("rectangle", (x + 1, top, x + w, base)), m, (30, 20, 10), 0.3)
    ic.outline(pts, 3, (40, 28, 16, 150))


def sapling(ic: Icon, x, base, h, s: float = 1.0, graft: bool = True, tone: float = 1.0) -> None:
    """Young grafted fruit tree tied to a stake: thin stem, waxed graft band, a few short limbs and a
    small open leafy crown."""
    rnd = ic.random
    top = base - h
    stake(ic, x + 11 * s, top + h * 0.1, base + 4, 12 * s)
    lean = rnd.uniform(-6, 6) * s
    stem = [(x, base), (x - 2, base - h * 0.35), (x + lean * 0.5, base - h * 0.7), (x + lean, top)]
    ic.line(stem, int(11 * s), (74, 52, 34))
    ic.line([(p[0] - 3 * s, p[1]) for p in stem], int(4 * s), (150, 112, 76, 110))
    # thin side twigs up the whip, a few bare
    side = rnd.choice((-1, 1))
    twigs = []
    for fy in (0.42, 0.58, 0.74, 0.86):
        sy = base - h * fy
        sx = x + lean * fy
        L = h * rnd.uniform(0.12, 0.2)
        a = math.radians(rnd.uniform(-60, -30)) if side > 0 else math.radians(rnd.uniform(-150, -120))
        ex, ey = sx + math.cos(a) * L, sy + math.sin(a) * L
        ic.line([(sx, sy), (ex, ey)], max(3, int(4 * s)), (84, 60, 40))
        twigs.append((ex, ey))
        side = -side
    cols = (scaled(YOUNG[0], tone), scaled(YOUNG[1], tone))
    # two or three small leaf clumps: at the leader and on the upper twigs
    clumps = [(x + lean + rnd.uniform(-4, 4), top + h * 0.08, h * 0.15)]
    clumps.append((twigs[2][0], twigs[2][1], h * rnd.uniform(0.1, 0.12)))
    if h > 250 or rnd.random() < 0.6:
        clumps.append((twigs[0][0], twigs[0][1], h * rnd.uniform(0.075, 0.09)))
    for cx, cy, r in sorted(clumps, key=lambda c: c[1], reverse=True):
        cm = crown(ic, cx, cy, r * 1.2, r * 0.95, cols, n=5, dabs=1.0)
        # bright yellow-green top light on the upper left of each clump
        tint(ic, ic.mask("ellipse", (cx - r * 1.4, cy - r * 1.3, cx + r * 0.5, cy + r * 0.1)), cm, (206, 226, 92), 0.42, 5)
    # tie to the stake
    ty = base - h * 0.5
    ic.line([(x - 5 * s, ty), (x + 17 * s, ty - 3)], int(5 * s), (150, 128, 80))
    if graft:  # pale grafting-wax band low on the stem
        gy = base - h * 0.2
        ic.fill(ic.mask("rectangle", (x - 8 * s, gy - 6 * s, x + 8 * s, gy + 6 * s)), "#e8d8a4", "#a08c60",
                radial=(x - 7 * s, gy - 7 * s, 22 * s), noise=0.08)
        ic.line([(x - 8 * s, gy + 6 * s), (x + 8 * s, gy + 6 * s)], 3, (90, 70, 40, 170))
    ic.shade(ic.mask("ellipse", (x - 30 * s, base - 8, x + 50 * s, base + 12)), alpha=0.35, blur=6, clip=False)


def soil(ic: Icon, pts, rows) -> Image.Image:
    """Raked nursery ground: dark tilled earth, furrows along the rows, clods and a few weeds."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, "#74482c", "#3e2414", (y0, y1), noise=0.34, chroma=0.12)
    for y in rows:  # dark furrow in front of each raised bed
        tint(ic, ic.mask("rectangle", (x0, y + 14, x1, y + 30)), m, (20, 10, 4), 0.4, 6)

    def clods(dr):
        for _ in range(420):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            r = rnd.uniform(3, 8) * (0.6 + 0.6 * (y - y0) / max(y1 - y0, 1))
            if rnd.random() < 0.5:
                dr.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(170, 140, 100, 90))
            else:
                dr.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(30, 20, 12, 90))
        for _ in range(30):  # weeds
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0 + 10, y1)
            for _ in range(5):
                a = rnd.uniform(-2.6, -0.5)
                L = rnd.uniform(8, 18)
                dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=(110, 130, 60, 200), width=3)

    ic.overlay(clods, m)
    return m


def wattle(ic: Icon, x0, x1, top, base) -> None:
    """Woven hazel hurdle: upright sails with withies woven in and out, lit tops, darker foot."""
    rnd = ic.random
    m = ic.mask("rectangle", (x0, top, x1, base))
    ic.fill(m, "#8a7252", "#4e3e2a", (top, base), noise=0.3)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y, k = top + 6, 0
    while y < base:
        x = x0
        while x < x1:
            w = rnd.uniform(34, 46)
            t = rnd.uniform(-1, 1)
            ph = (k + int((x - x0) / 40)) % 2
            d.ellipse((x - 4, y - 7, x + w + 4, y + 9), fill=(196, 170, 126, 90 + int(20 * t)) if ph else (40, 28, 16, 70))
            d.line([(x + 4, y - 4), (x + w - 4, y - 5)], fill=(226, 206, 160, 70), width=3)
            x += w
        y += 16
        k += 1
    paste_clipped(ic, lay, m)
    tint(ic, ic.mask("rectangle", (x0, base - 30, x1, base + 10)), m, (20, 14, 8), 0.4, 10)
    for x in np.arange(x0 + 10, x1, 70):
        ic.rect((x - 7, top - 14 + rnd.uniform(-4, 4), x + 7, base), "#9a7e58", "#5a4430", vertical=False, edge=3)
    ic.outline([(x0, top), (x1, top), (x1, base), (x0, base)], 4, (40, 28, 16, 150))


def pot(ic: Icon, cx, base, w, h, upturned: bool = False) -> Image.Image:
    """Terracotta flowerpot: tapered body lit from the left, a rolled rim, dark earth or the base on top."""
    if upturned:
        pts = [(cx - w * 0.36, base - h), (cx + w * 0.36, base - h), (cx + w * 0.5, base - h * 0.18),
               (cx + w * 0.5, base), (cx - w * 0.5, base), (cx - w * 0.5, base - h * 0.18)]
    else:
        pts = [(cx - w * 0.5, base - h), (cx + w * 0.5, base - h), (cx + w * 0.5, base - h * 0.8),
               (cx + w * 0.36, base), (cx - w * 0.36, base), (cx - w * 0.5, base - h * 0.8)]
    m = ic.poly_mask(pts)
    ic.fill(m, CLAY[0], CLAY[1], (cx - w * 0.55, cx + w * 0.5), vertical=False, noise=0.18, chroma=0.1)
    ic.fill(ic.mask("ellipse", (cx - w * 0.5, base - h - h * 0.12, cx + w * 0.5, base - h + h * 0.12)), "#cf8a5e", "#8a4a2a",
            noise=0.12)
    if not upturned:
        ic.fill(ic.mask("ellipse", (cx - w * 0.4, base - h - h * 0.07, cx + w * 0.4, base - h + h * 0.08)), "#3a2a1c",
                "#1e140c", noise=0.2)
    rim = h * (0.8 if upturned else 0.2)
    ic.line([(cx - w * 0.5, base - h + (h - rim if upturned else rim)), (cx + w * 0.5, base - h + (h - rim if upturned else rim))],
            4, (70, 30, 14, 150))
    tint(ic, ic.mask("rectangle", (cx - w * 0.33, base - h, cx - w * 0.2, base)), m, (255, 220, 190), 0.2, 4)
    ic.outline(pts, 3, (50, 24, 12, 160))
    ic.shade(ic.mask("ellipse", (cx - w * 0.4, base - 6, cx + w * 0.8, base + 10)), alpha=0.4, blur=5, clip=False)
    return m


def seedling(ic: Icon, cx, top, s: float = 1.0) -> None:
    """Grafted whip in a pot: a thin stem and a small tuft of leaves."""
    ic.line([(cx, top + 40 * s), (cx + 2, top)], int(7 * s), (78, 58, 40))
    for deg, L in ((-150, 36), (-100, 40), (-40, 36), (-70, 30), (-125, 28)):
        a = math.radians(deg)
        x2, y2 = cx + math.cos(a) * L * s, top + 4 + math.sin(a) * L * s
        ic.fill(ic.poly_mask([(cx, top + 6), (cx + (x2 - cx) * 0.5 - 7, top + (y2 - top) * 0.5), (x2, y2),
                              (cx + (x2 - cx) * 0.5 + 7, top + (y2 - top) * 0.5 + 4)]), YOUNG[0], YOUNG[1],
                radial=(cx - 20, top - 30, 60 * s), noise=0.2)


# ---------------------------------------------------------------- parts
def ground(ic: Icon) -> None:
    rnd = ic.random
    top = [(14, 648)] + [(x, 640 + rnd.uniform(-8, 8)) for x in np.linspace(80, 560, 8)] + [(600, 700), (600, 1000)]
    pts = top + [(20, 1000)]
    soil(ic, pts, (712, 812, 930))
    # grass verge in front of the shed
    verge = [(560, 880), (1010, 872), (1014, 998), (560, 1004)]
    ic.poly(verge, "#6e7040", "#4a4a28", noise=0.3, edge=3)

    def grass(dr):
        for _ in range(160):
            x, y = rnd.uniform(560, 1010), rnd.uniform(880, 996)
            a = rnd.uniform(-2.4, -0.7)
            L = rnd.uniform(8, 18)
            col = (170, 170, 100, 150) if rnd.random() < 0.5 else (50, 56, 26, 150)
            dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(grass, ic.poly_mask(verge))


def shed(ic: Icon) -> None:
    rnd = ic.random
    X0, X1, WT, WB = 590, 986, 590, 884
    # rear posts, board walls, dark doorway and an open hatch
    walls = [(X0, WT), (X1, WT), (X1, WB), (X0, WB)]
    wm = planks(ic, walls, "#8e6a46", "#553a24", board=30)
    tint(ic, ic.mask("rectangle", (X0, WB - 70, X1, WB + 10)), wm, (40, 44, 20), 0.35, 16)
    # open front bay behind the potting bench: the dark shed interior, a shelf and pots in the gloom
    bay = [(X0 + 22, 758), (838, 758), (838, WB), (X0 + 22, WB)]
    ic.fill(ic.poly_mask(bay), "#30241a", "#140e08", (758, WB), noise=0.14)
    ic.line([(X0 + 24, 800), (836, 800)], 6, (74, 54, 36, 200))
    for px in (700, 770):
        ic.fill(ic.mask("ellipse", (px - 14, 772, px + 14, 800)), "#5a3422", "#2a160c", noise=0.1)
    ic.shade(ic.mask("rectangle", (X0 + 22, 758, 838, 790)), alpha=0.5, blur=6)
    timber(ic, (X0 + 18, 752), (842, 752), 14, "#8a6440", "#4e3522")
    door = [(846, 676), (930, 676), (930, WB), (846, WB)]
    ic.fill(ic.poly_mask(door), "#2a2018", "#120c08", (676, WB), noise=0.12)
    ic.shade(ic.mask("rectangle", (846, 676, 930, 700)), alpha=0.5, blur=4)
    # a hand tool leaning inside the door, pale blade catching light
    ic.line([(872, 700), (898, WB - 8)], 7, (120, 92, 60))
    ic.fill(ic.poly_mask([(890, WB - 50), (908, WB - 50), (906, WB - 6), (888, WB - 8)]), "#9aa0a0", "#4c5052", noise=0.1)
    for x in (846, 930):
        timber(ic, (x, 668), (x, WB), 16, "#8a6440", "#4e3522")
    timber(ic, (840, 672), (936, 672), 16, "#8a6440", "#4e3522")
    hatch = [(650, 660), (790, 660), (790, 740), (650, 740)]
    ic.fill(ic.poly_mask(hatch), "#2c2218", "#16100a", (660, 740), noise=0.12)
    # pots on a shelf inside the hatch
    for px in (672, 712, 752):
        pot(ic, px, 732, 34, 30)
    ic.shade(ic.mask("rectangle", (650, 660, 790, 690)), alpha=0.5, blur=4)
    timber(ic, (644, 744), (796, 744), 14, "#94704a", "#5a3e26")
    for x in (X0 + 8, X1 - 8):
        timber(ic, (x, WT - 6), (x, WB), 20, "#86603e", "#4a3220")
    # roof of split wooden shingles, eave casting a shadow on the boards
    # lower-pitched roof of split wooden shingles, warm log-cabin brown
    RT = 378
    roof = [(676, RT + 4), (914, RT), (1012, 612), (566, 618)]
    rm = shingles(ic, roof, "#b07a4a", "#643c20", course=30, stagger=34)
    # value bands: sunlit upper courses, mid, a darker weathered band towards the eave
    tint(ic, ic.mask("rectangle", (0, RT, SIZE, RT + 70)), rm, (255, 214, 160), 0.16, 10)
    tint(ic, ic.mask("rectangle", (0, 500, SIZE, 560)), rm, (40, 20, 8), 0.18, 10)
    tint(ic, ic.mask("rectangle", (0, 560, SIZE, 620)), rm, (30, 14, 6), 0.3, 8)
    for _ in range(10):  # lichen and weathering
        x, y = rnd.uniform(620, 990), rnd.uniform(RT + 20, 590)
        r = rnd.uniform(10, 22)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), rm,
             (196, 180, 120) if rnd.random() < 0.5 else (40, 24, 12), 0.16, 4)
    ic.shade(ic.mask("rectangle", (X0, WT, X1, WT + 60)), alpha=0.55, blur=14)
    ic.line([(676, RT + 4), (914, RT)], 16, (138, 96, 58))
    ic.line([(680, RT - 2), (910, RT - 6)], 4, (214, 170, 116))
    ic.line([(574, 600), (1004, 594)], 8, (44, 24, 12, 170))  # eave shadow line
    ic.line([(566, 618), (1012, 612)], 10, (84, 54, 30))


def bench(ic: Icon) -> None:
    """Potting bench in front of the shed: pots with grafted whips, a crock of grafting wax."""
    T = 812
    for x in (640, 790):
        timber(ic, (x, T), (x, 922), 16, "#86603e", "#4a3220")
    ic.shade(ic.mask("rectangle", (620, 900, 820, 930)), alpha=0.4, blur=8)
    top = [(622, T - 16), (812, T - 18), (818, T + 8), (618, T + 10)]
    ic.poly(top, "#a88258", "#6a4c30", edge=4)
    for x, s in ((656, 0.9), (700, 1.0), (752, 0.95)):
        pot(ic, x, T - 4, 40 * s, 38 * s)
        seedling(ic, x, T - 110 * s, s)
    # crock of grafting wax
    ic.fill(ic.mask("ellipse", (784, T - 52, 812, T - 4)), "#8c7a60", "#3e3226", radial=(788, T - 48, 34), noise=0.15)
    ic.fill(ic.mask("ellipse", (786, T - 56, 810, T - 44)), "#d8c890", "#9a8a58", noise=0.1)


def front_props(ic: Icon) -> None:
    rnd = ic.random
    # stack of upturned pots, larger, and a spare pot on its side
    for i, (x, b) in enumerate(((800, 1000), (800, 950), (800, 902))):
        pot(ic, x, b, 92 - i * 6, 56, upturned=True)
    pot(ic, 728, 1000, 60, 50)
    # big basket of apples from the old orchard
    bx0, bx1, by0, by1 = 846, 1018, 852, 1000
    ic.shade(ic.mask("ellipse", (bx0 - 10, by1 - 30, bx1 + 6, by1 + 8)), alpha=0.5, blur=8)
    ic.fill(ic.mask("ellipse", (bx0 + 6, by0 - 20, bx1 - 6, by0 + 26)), "#3a2412", "#20140a")
    heap = []
    cx = (bx0 + bx1) / 2
    for _ in range(30):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        heap.append((cx + math.cos(a) * 66 * rr, by0 + 2 + math.sin(a) * 44 * rr + rnd.uniform(0, 10), rnd.uniform(20, 25),
                     rnd.choice((APPLE, APPLE, APPLE2, GOLD))))
    fruit(ic, heap)
    ic.basket(bx0, by0, bx1, by1)
    # a few windfalls beside it
    fruit(ic, [(836, 992, 20, APPLE)])


def bed(ic: Icon, base: float, s: float) -> None:
    """Raised nursery bed: a mound of dug earth with a lit top and a dark furrow in front."""
    rnd = ic.random
    top = [(16, base - 24 * s)] + [(x, base - 30 * s + rnd.uniform(-4, 4)) for x in np.linspace(60, 560, 9)]
    top += [(600, base - 20 * s)]
    front = [(600, base + 14 * s), (16, base + 16 * s)]
    m = ic.poly_mask(top + front)
    # ridge of dug earth in the soil's own value: soft top-lit crest, darker flank, dark furrow shadow
    ic.fill(m, "#86563a", "#3e2414", (base - 30 * s, base + 16 * s), noise=0.36, chroma=0.12)
    tint(ic, ic.mask("rectangle", (0, base - 36 * s, SIZE, base - 20 * s)), m, (236, 176, 120), 0.14, 8)
    tint(ic, ic.mask("rectangle", (0, base + 2 * s, SIZE, base + 20 * s)), m, (24, 12, 6), 0.3, 6)
    ic.shade(ic.mask("rectangle", (16, base + 12 * s, 600, base + 34 * s)), (18, 8, 4), 0.55, blur=7)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.84

    shed(ic)
    ground(ic)
    # three beds of saplings: back row smaller and duller, front row biggest
    rows = [(700, 226, 0.72, 0.86, (56, 178, 312, 440, 540)),
            (814, 290, 0.86, 0.94, (112, 250, 384, 510)),
            (936, 350, 1.0, 1.0, (70, 226, 392))]
    for base, h, s, tone, xs in rows:
        bed(ic, base, s)
        for i, x in enumerate(xs):
            sapling(ic, x + rnd.uniform(-14, 14), base + rnd.uniform(-4, 4), h * rnd.uniform(0.8, 1.12), s,
                    graft=(i % 2 == 0), tone=tone * rnd.uniform(0.94, 1.08))
    bench(ic)
    front_props(ic)
