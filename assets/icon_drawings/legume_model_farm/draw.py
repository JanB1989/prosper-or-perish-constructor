"""Legume Model Farm (tier 3 of the legume farm chain): a brick farmhouse with a slate roof and a brick
barn behind a field of drilled pulse rows fenced along its side, an iron-bound seed chest with its ledger and sacks of beans.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/legume_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/legume_model_farm

Identity: the chain's podded pulse bushes, now drilled in straight rows running away from the
viewer on a railed field (the building's drilled rows), in front of a symmetrical brick farmhouse
with a grey slate roof and twin chimneys and a brick barn; a seed chest with the seed ledger on its
lid, tied seed sacks and an open sack of beans at the bottom right.

Local helpers shared by the legume family: ``pulse_bush``, ``pod``, ``beans`` / ``bean_heap_items``,
``bean_sack``, ``soil``; field slab helpers (``Field``, ``slab_face``) from field_management;
generic ones copied from cookshop / tavern / victualling_yard.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

# ---------------------------------------------------------------- shared legume-family palette
PEA_LEAF = ((60, 104, 70), (116, 156, 112), (18, 38, 28))  # glaucous pea/bean foliage: mid, lit, dark
POD = ("#8cc83a", "#4a8a1a")  # fresh green pods
POD_DRY = ("#c8b27a", "#7a6034")  # a few ripening, straw-coloured pods
BEANS = (  # (mid, lit, dark, speckle): haricot, fava, borlotti, green pea, lentil
    ((222, 206, 166), (246, 236, 208), (130, 112, 80), None),
    ((170, 136, 86), (208, 180, 126), (92, 68, 38), None),
    ((196, 160, 132), (228, 204, 178), (110, 80, 62), (120, 50, 40)),
    ((140, 164, 78), (186, 204, 120), (70, 90, 34), None),
    ((188, 120, 64), (222, 164, 104), (104, 60, 28), None),
)
BURLAP = ("#b89c6a", "#5a4428")
TIMBER = ("#86603e", "#4e3522")
SOIL = ("#77603f", "#4a3a26")


# ---------------------------------------------------------------- generic helpers (from cookshop / tavern / victualling_yard)
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)


def dk(c, f: float):
    return tuple(int(v * f) for v in rgb(c))


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form: tone variation, lit top-left edge, shadowed bottom-right edge."""
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


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow = blank()
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
    ic.outline(pts, edge)
    return m


def thatch(ic: Icon, pts, c1="#b49a64", c2="#5e4a2a", course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands down the slope, layered courses, weathered blotches. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    shadow = blank()
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    paste_clipped(ic, lay, m)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col, rnd(0.08, 0.2), 18)
    return m


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, max(w - 4, 5))
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    paste_clipped(ic, lay, m)


def timber(ic: Icon, p0, p1, width: float, c1=TIMBER[0], c2=TIMBER[1]) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def bricks(ic: Icon, m: Image.Image, box, base="#94604a", dark="#5c3a2c", course: float = 17, length: float = 40) -> None:
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


def profile(cx, top, h, w, knots, n=28):
    """Closed outline of a turned vessel from (s, half-width fraction) knots, s = 0 at the top."""
    ss = np.linspace(0, 1, n)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    return [(cx - v, top + h * s) for s, v in zip(ss, hw)] + [(cx + v, top + h * s) for s, v in zip(ss[::-1], hw[::-1])]


def crock(ic: Icon, cx, base, w, h, body=("#a98a6a", "#4a3727"), cloth=("#ddd0b4", "#978667")) -> None:
    """Stoneware seed jar sealed with a tied cloth."""
    knots = [(0, 0.30), (0.1, 0.31), (0.2, 0.44), (0.38, 0.5), (0.62, 0.49), (0.9, 0.42), (1.0, 0.37)]
    pts = profile(cx, base - h, h, w, knots, 26)
    ty = base - h
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - w * 0.28, ty + h * 0.4, w * 1.05), noise=0.14)
    tint(ic, ic.mask("rectangle", (cx + w * 0.12, ty, cx + w, base)), m, (20, 12, 6), 0.3, 12)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, ty + h * 0.3, cx - w * 0.2, ty + h * 0.62)), m, (255, 240, 220), 0.3, 5)
    ic.line([(cx - w * 0.47, ty + h * 0.42), (cx + w * 0.47, ty + h * 0.44)], 3, (60, 40, 24, 120))
    ic.outline(pts, 4, (44, 30, 20, 170))
    lid = [(cx - w * 0.38, ty + h * 0.2), (cx - w * 0.36, ty + h * 0.04), (cx - w * 0.2, ty - h * 0.08),
           (cx + w * 0.02, ty - h * 0.11), (cx + w * 0.24, ty - h * 0.07), (cx + w * 0.37, ty + h * 0.04),
           (cx + w * 0.4, ty + h * 0.22), (cx + w * 0.1, ty + h * 0.16), (cx - w * 0.12, ty + h * 0.23)]
    ic.fill(ic.poly_mask(lid), cloth[0], cloth[1], radial=(cx - w * 0.2, ty - h * 0.08, w * 0.8), noise=0.1)
    ic.outline(lid, 3, (70, 58, 40, 170))
    ic.line([(cx - w * 0.34, ty + h * 0.08), (cx + w * 0.35, ty + h * 0.09)], 5, (92, 62, 38))


def sack(ic: Icon, cx, base, w, h, c=BURLAP, lean: float = 0) -> Image.Image:
    """Filled tied sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    for f in (-0.18, 0.12):
        ic.line([(cx + w * f, base - h * 0.78), (cx + w * f * 1.6, base - h * 0.2)], 3, (70, 58, 40, 90))
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.2, base - h * 0.8), (nx - w * 0.1, base - h * 0.93), (nx - w * 0.24, base - h * 1.02),
            (nx - w * 0.04, base - h * 0.99), (nx + w * 0.22, base - h * 1.05), (nx + w * 0.11, base - h * 0.93),
            (nx + w * 0.21, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.12, base - h * 0.9), (nx + w * 0.12, base - h * 0.89)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))
    return body


def hay(ic: Icon, pts, strands: int = 220) -> Image.Image:
    """Loose hay / fodder: golden mass lit top-left, dark underside, straw strokes."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#c8ac68", "#62502a", radial=(min(xs) + (max(xs) - min(xs)) * 0.3, min(ys), (max(ys) - min(ys)) * 1.4),
            noise=0.22)
    rnd = ic.random.uniform

    def straw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(strands):
            x, y = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
            a = rnd(-0.9, 0.9) + (math.pi if ic.random.random() < 0.5 else 0)
            ln = rnd(14, 40)
            t = rnd(-1, 1)
            col = (255, 240, 180, int(t * 110)) if t > 0 else (50, 34, 10, int(-t * 110))
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (min(xs), (min(ys) + max(ys)) / 2 + 10, max(xs), max(ys))), m, (30, 16, 4), 0.35, 16)
    return m


# ---------------------------------------------------------------- legume helpers (new for this family)
def beans(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Pulses as small shaded ovals in one blended layer: (x, y, size, palette index).

    Kidney/fava beans are ovals turned at random, peas and lentils round; speckled beans get specks."""
    rnd = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for x, y, s, k in items:
            mid, lit, dark, speck = BEANS[k]
            rx, ry = (s, s) if k in (3, 4) else (s * 1.35, s * 0.9)
            a = rnd.uniform(0, math.pi)
            ca, sa = math.cos(a), math.sin(a)

            def ell(dx, dy, fx, fy):
                return [(x + dx + math.cos(t) * rx * fx * ca - math.sin(t) * ry * fy * sa,
                         y + dy + math.cos(t) * rx * fx * sa + math.sin(t) * ry * fy * ca)
                        for t in np.linspace(0, 2 * math.pi, 14, endpoint=False)]

            d.polygon(ell(1.5, 2.5, 1.0, 1.0), fill=dark + (230,))
            d.polygon(ell(0, 0, 0.92, 0.9), fill=mid + (255,))
            d.polygon(ell(-rx * 0.25, -ry * 0.3, 0.45, 0.4), fill=lit + (200,))
            if speck:
                for _ in range(3):
                    sx, sy = x + rnd.uniform(-rx, rx) * 0.6, y + rnd.uniform(-ry, ry) * 0.6
                    d.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=speck + (200,))

    ic.overlay(paint, clip)


def bean_heap_items(ic: Icon, cx, cy, rx, ry, size, weights=(3, 2, 1, 2, 1)):
    """Bean positions over an elliptic heap top, back to front (smaller at the back)."""
    rnd = ic.random
    pool = [k for k, w in enumerate(weights) for _ in range(w)]
    items = []
    y = cy - ry
    while y < cy + ry:
        f = (y - (cy - ry)) / (2 * ry)
        half = rx * math.sqrt(max(0.0, 1 - ((y - cy) / ry) ** 2))
        s = size * (0.8 + 0.25 * f)
        x = cx - half + rnd.uniform(0, s)
        while x < cx + half:
            items.append((x + rnd.uniform(-2, 2), y + rnd.uniform(-2, 2), s * rnd.uniform(0.85, 1.1), rnd.choice(pool)))
            x += s * rnd.uniform(1.9, 2.4)
        y += s * 1.1
    return items


def bean_sack(ic: Icon, cx, base, w, h, c=BURLAP, weights=(3, 2, 1, 2, 1), bean: float = 11) -> Image.Image:
    """Open burlap sack with a rolled lip, heaped with mixed pulses. Returns the body mask."""
    top = base - h
    knots = [(0, 0.44), (0.08, 0.47), (0.45, 0.52), (0.85, 0.52), (1, 0.47)]
    pts = profile(cx, top, h, w, knots, 30)
    pts = [(x + ic.random.uniform(-2, 2), y + ic.random.uniform(-2, 2)) for x, y in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], radial=(cx - w * 0.28, top + h * 0.35, w * 1.0), noise=0.14, chroma=0.05)
    tint(ic, ic.mask("rectangle", (cx + w * 0.1, top, cx + w, base)), m, (20, 12, 4), 0.32, 16)
    folds = blank()
    fd = ImageDraw.Draw(folds)
    for f in (-0.24, 0.02, 0.26):
        x = cx + w * f
        fd.line([(x, top + h * 0.3), (x + w * 0.06, base - h * 0.08)], fill=255, width=6)
    tint(ic, folds, m, (40, 26, 12), 0.3, 5)

    def weave(d):
        for k in range(10):
            y = top + h * (0.25 + 0.07 * k)
            d.line([(cx - w * 0.5, y), (cx + w * 0.5, y + 3)], fill=(50, 36, 20, 45), width=2)

    ic.overlay(weave, m)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.14, cx + w, base + 4)), m, (20, 12, 4), 0.35, 8)
    ic.outline(pts, 4, (60, 44, 26, 180))
    # rolled-down lip, then the heap of beans rising above it
    lip = (cx - w * 0.49, top - h * 0.05, cx + w * 0.49, top + h * 0.17)
    ic.fill(ic.mask("ellipse", lip), "#d8c49a", "#8a7450", (lip[1], lip[3]), noise=0.2)
    ic.overlay(lambda d: d.ellipse(lip, outline=(60, 44, 26, 170), width=4))
    inner = (cx - w * 0.42, top - h * 0.02, cx + w * 0.42, top + h * 0.12)
    heap = [(cx + math.cos(a) * w * 0.42, top + h * 0.05 + math.sin(a) * h * 0.24)
            for a in np.linspace(math.pi, 2 * math.pi, 24)]
    hm = union(ic.poly_mask(heap), ic.mask("ellipse", inner))
    ic.fill(hm, "#a88a60", "#5a4228", (top - h * 0.2, top + h * 0.12), noise=0.2)
    beans(ic, bean_heap_items(ic, cx, top - h * 0.02, w * 0.42, h * 0.16, bean, weights), hm)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, top - h * 0.1, cx + w * 0.6, top + h * 0.2)), hm, (20, 12, 4), 0.25, 10)
    return m


def pod(ic: Icon, top, deg: float, length: float, width: float, colors=POD, peas: int = 4, curl: float = 0.22) -> None:
    """A hanging pea/bean pod from its stalk at ``top`` towards ``deg`` (90 = straight down): a short fat
    crescent, rounded at the stalk and beaked at the tip, bulging over each seed. Fresh green body, a
    darker green edge on the shadow side, a small light highlight on the lit side. ``curl`` < 0 bows it
    the other way."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    if n[0] > 0:  # n points to the viewer's left (the lit side)
        n = -n
    b = np.array(top, float)
    ts = np.linspace(0, 1, 40)
    spine = [b + d * length * t + n * curl * length * math.sin(math.pi * t) for t in ts]

    def body(t):
        if t < 0.16:
            return 0.35 + 0.65 * math.sqrt(t / 0.16)
        if t > 0.72:
            return max(0.0, (1 - t) / 0.28) ** 0.85
        return 1.0

    def bump(t):
        if not 0.12 < t < 0.8:
            return 1.0
        return 0.93 + 0.14 * (0.5 + 0.5 * math.cos(2 * math.pi * peas * (t - 0.12) / 0.68 + math.pi))

    hw = [width / 2 * body(t) for t in ts]
    bb = [bump(t) for t in ts]
    s1 = [p + n * w * k for p, w, k in zip(spine, hw, bb)]  # lit side
    s2 = [p - n * w for p, w in zip(spine, hw)]  # shadow side
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], (min(ys), max(ys)), noise=0.1, chroma=0.06)
    # shadow half, then a darker band right along the shadow edge
    shadow = [tuple(p - n * w * 0.05) for p, w in zip(spine, hw)] + [tuple(p) for p in s2[::-1]]
    ic.shade(ic.intersect(ic.poly_mask(shadow), m), (16, 40, 6), 0.42)
    edge = [tuple(p - n * w * 0.55) for p, w in zip(spine, hw)] + [tuple(p) for p in s2[::-1]]
    ic.shade(ic.intersect(ic.poly_mask(edge), m), (10, 30, 4), 0.5)
    # the bulge over each seed: a light cap on the lit half, a dark crease between seeds
    for k in range(peas):
        t = 0.12 + 0.68 * (k + 0.5) / peas
        i = int(t * 39)
        p = spine[i] + n * hw[i] * 0.28
        r = hw[i] * 0.5
        ic.shade(ic.intersect(ic.mask("ellipse", (p[0] - r, p[1] - r, p[0] + r, p[1] + r)), m), (226, 248, 160), 0.3, blur=1.5)
    hi = [tuple(spine[i] + n * hw[i] * 0.5 * bb[i]) for i in range(int(0.2 * 39), int(0.55 * 39))]
    ic.line(hi, max(3, int(width * 0.16)), (232, 250, 184, 170))
    ic.outline(pts, 3, (18, 40, 8, 190))
    ic.line([tuple(b - d * 14 + n * 5), tuple(b + d * 6)], 5, (58, 84, 30))


def pulse_bush(ic: Icon, cx: float, base: float, w: float, h: float, pods: int = 4, leaf=PEA_LEAF,
               leaflet: float = 12, flowers: int = 2, dry: float = 0.0, pod_scale: float = 1.0,
               bloom=((224, 216, 222), (200, 184, 206))) -> Image.Image:
    """Low bushy pea/bean plant: dome of small oval leaflets lit from the upper left, white flowers on top,
    3-5 fat pods hanging in one or two clusters from mid-height over the front. Returns the bush mask."""
    rnd = ic.random
    top = [(cx + u * w / 2, base - h * (max(0.0, 1 - u * u) ** 0.55) * rnd.uniform(0.9, 1.06))
           for u in np.linspace(-1, 1, 15)]
    body = ic.poly_mask(top + [(cx + w / 2, base), (cx - w / 2, base)])
    ic.fill(body, dk(leaf[0], 0.75), dk(leaf[2], 0.7), radial=(cx - w * 0.3, base - h, h * 1.4), noise=0.3)
    mid, lit, dark = leaf
    items = []
    n = int(w * h / (leaflet * leaflet) * 0.55)
    for _ in range(n):
        u, v = rnd.uniform(-1, 1), rnd.uniform(0, 1)
        prof = max(0.0, 1 - u * u) ** 0.55
        if v > prof * 1.04:
            continue
        x = cx + u * w / 2
        y = base - h * v
        light = 0.5 - 0.5 * u * 0.8 + 0.6 * (v - 0.5)
        items.append((x, y, leaflet * rnd.uniform(0.75, 1.2), light + rnd.uniform(-0.35, 0.35), rnd.uniform(0, math.pi)))
    items.sort(key=lambda it: it[1])

    def mix(c0, c1, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(a * (1 - t) + b * t) for a, b in zip(c0, c1))

    def paint(d: ImageDraw.ImageDraw) -> None:
        for x, y, r, light, ang in items:
            ca, sa = math.cos(ang), math.sin(ang)

            def ell(dx, dy, f):
                return [(x + dx + math.cos(t) * r * f * ca - math.sin(t) * r * 0.62 * f * sa,
                         y + dy + math.cos(t) * r * f * sa + math.sin(t) * r * 0.62 * f * ca)
                        for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]

            col = mix(dark, mid, light * 1.6) if light < 0.62 else mix(mid, lit, (light - 0.62) * 2.2)
            d.polygon(ell(2, 3, 1.05), fill=dark + (200,))
            d.polygon(ell(0, 0, 1.0), fill=col + (255,))
            d.polygon(ell(-r * 0.2, -r * 0.18, 0.45), fill=mix(col, lit, 0.5) + (150,))

    ic.overlay(paint)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.28, cx + w, base + 6)), body, (10, 16, 4), 0.35, 12)
    fl = []
    for _ in range(flowers):
        u = rnd.uniform(-0.7, 0.7)
        fl.append((cx + u * w / 2, base - h * (max(0.0, 1 - u * u) ** 0.55) * rnd.uniform(0.75, 0.95)))

    def petals(d):
        for x, y in fl:
            d.ellipse((x - 9, y - 5, x + 1, y + 4), fill=bloom[0] + (235,))
            d.ellipse((x - 2, y - 7, x + 8, y + 3), fill=bloom[1] + (235,))

    ic.overlay(petals)
    pods = min(pods, 5)
    if pods <= 0:
        return body
    # one or two clusters hung from mid-height; each pod a short fat crescent
    us = [rnd.uniform(-0.15, 0.15)] if pods <= 3 else [rnd.uniform(-0.5, -0.28), rnd.uniform(0.24, 0.46)]
    split = [pods] if len(us) == 1 else [pods - pods // 2, pods // 2]
    L0 = h * 0.44 * pod_scale
    for u0, k in zip(us, split):
        sx0 = cx + u0 * w / 2
        sy0 = base - h * rnd.uniform(0.54, 0.64)
        order = sorted(range(k), key=lambda j: -abs(j - (k - 1) / 2))  # outer pods first, middle in front
        for j in order:
            off = j - (k - 1) / 2
            ang = 90 + off * 16 + u0 * 12 + rnd.uniform(-6, 6)
            L = L0 * rnd.uniform(0.86, 1.08)
            sx, sy = sx0 + off * w * 0.13, sy0 + abs(off) * h * 0.05 + rnd.uniform(-3, 3)
            colors = POD_DRY if rnd.random() < dry else POD
            ex = L * math.cos(math.radians(ang))
            ic.shade(ic.poly_mask([(sx + 6, sy + 6), (sx + L * 0.27, sy + 6), (sx + L * 0.27 + ex, sy + L + 4),
                                   (sx + 6 + ex, sy + L + 4)]), (4, 12, 2), 0.35, blur=6)
            pod(ic, (sx, sy), ang, L, L * 0.27, colors, rnd.choice((3, 4, 4)),
                (1 if rnd.random() < 0.5 else -1) * rnd.uniform(0.14, 0.22))
    return body


def soil(ic: Icon, pts, c=SOIL, furrows=None, clods: int = 60) -> Image.Image:
    """Earth patch: gradient, clods, optional furrow lines (list of polylines). Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.32, chroma=0.08)
    rnd = ic.random
    if furrows:
        def fur(d):
            for line in furrows:
                d.line(line, fill=(30, 20, 10, 110), width=9)
                d.line([(x, y - 7) for x, y in line], fill=(200, 170, 120, 60), width=5)
        ic.overlay(fur, m)

    def cl(d):
        for _ in range(clods):
            x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
            r = rnd.uniform(4, 9)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(214, 186, 140, 60) if rnd.random() < 0.5 else (20, 12, 6, 70))

    ic.overlay(cl, m)
    return m


# ---------------------------------------------------------------- field slab helpers (from field_management)
GOLD = ("#d8a040", "#8a5c20")


class Field:
    """Field slab top seen from the raised camera: (u, v) in [0, 1]^2, u across, v from back to front."""

    def __init__(self, bl, br, fl, fr, persp: float = 1.25):
        self.bl, self.br, self.fl, self.fr = (np.array(p, float) for p in (bl, br, fl, fr))
        self.persp = persp

    def P(self, u: float, v: float) -> tuple[float, float]:
        v = v ** self.persp
        back = self.bl + (self.br - self.bl) * u
        front = self.fl + (self.fr - self.fl) * u
        p = back + (front - back) * v
        return float(p[0]), float(p[1])

    def band(self, v0: float, v1: float, u0: float = 0.0, u1: float = 1.0, n: int = 24) -> list:
        top = [self.P(u, v0) for u in np.linspace(u0, u1, n)]
        bot = [self.P(u, v1) for u in np.linspace(u1, u0, n)]
        left = [self.P(u0, v) for v in np.linspace(v1, v0, 8)[1:-1]]
        right = [self.P(u1, v) for v in np.linspace(v0, v1, 8)[1:-1]]
        return top + right + bot + left

    def mask(self, ic: Icon, v0=0.0, v1=1.0, u0=0.0, u1=1.0) -> Image.Image:
        return ic.poly_mask(self.band(v0, v1, u0, u1))

    def scale(self, v: float) -> float:
        return 0.5 + 0.5 * v


def slab_face(ic: Icon, F: Field, depth: float = 64) -> Image.Image:
    """Cut earth below the front edge: lit lip, dark strata, stones and root ends."""
    rnd = ic.random
    edge = [F.P(u, 1.0) for u in np.linspace(0, 1, 30)]
    edge = [(x, y + rnd.uniform(-3, 3)) for x, y in edge]
    low = [(x + rnd.uniform(-4, 4), y + depth + rnd.uniform(-8, 10)) for x, y in edge[::-1]]
    pts = edge + low
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, "#6a5038", "#34261a", (min(ys), max(ys)), noise=0.3, chroma=0.12)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(3):
        f = 0.3 + 0.25 * k
        line = [(x, y + depth * f + rnd.uniform(-4, 4)) for x, y in edge[::2]]
        d.line(line, fill=(30, 20, 12, 90), width=4, joint="curve")
    for _ in range(40):
        x = rnd.uniform(edge[0][0], edge[-1][0])
        y = np.interp(x, [p[0] for p in edge], [p[1] for p in edge]) + rnd.uniform(12, depth - 6)
        r = rnd.uniform(4, 10)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(150, 136, 116, 170))
        d.ellipse((x - r * 0.6, y - r * 0.6, x + r * 0.2, y), fill=(200, 188, 168, 120))
    for _ in range(14):
        x = rnd.uniform(edge[0][0], edge[-1][0])
        y = np.interp(x, [p[0] for p in edge], [p[1] for p in edge]) + rnd.uniform(6, 20)
        d.line([(x, y), (x + rnd.uniform(-14, 14), y + rnd.uniform(12, 30))], fill=(40, 28, 16, 150), width=3)
    paste_clipped(ic, lay, m)
    tint(ic, ic.poly_mask(edge + [(x, y + 16) for x, y in edge[::-1]]), m, (255, 236, 200), 0.18, 4)
    tint(ic, ic.poly_mask([(x, y + depth * 0.6) for x, y in edge] + low), m, (0, 0, 0), 0.3, 10)
    ic.outline(pts, 3, (40, 28, 16, 150))
    return m


def grain(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, h: float = 54, colors=GOLD) -> Image.Image:
    """Standing cereal: gold base, dense stalk strokes with lit ears, the back row breaking the edge."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, colors[0], colors[1], (min(ys) - 20, max(ys) + 30), noise=0.28, chroma=0.12)
    lit = tuple(min(255, int(v * 1.2)) for v in rgb(colors[0]))
    shd = dk(colors[1], 0.62)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rows = max(3, int((v1 - v0) * 26))
    for i in range(rows + 1):
        v = v0 + (v1 - v0) * i / rows
        s = F.scale(v)
        hh = h * s
        u = u0 + rnd.uniform(0, 0.012)
        while u < u1:
            x, y = F.P(u, v)
            y += rnd.uniform(-3, 3)
            top = (x + rnd.uniform(-5, 5), y - hh * rnd.uniform(0.75, 1.05))
            d.line([(x, y), top], fill=shd + (150,), width=4)
            d.line([(x - 2, y - hh * 0.25), (top[0] - 2, top[1] + 4)], fill=lit + (140,), width=3)
            d.ellipse((top[0] - 5 * s, top[1] - 11 * s, top[0] + 5 * s, top[1] + 9 * s),
                      fill=(lit if rnd.random() < 0.6 else tuple(int(c) for c in rgb(colors[0]))) + (200,))
            u += rnd.uniform(0.008, 0.016) / s
    paste_clipped(ic, lay, union(m, F.mask(ic, max(0, v0 - 0.12), v0 + 0.02, u0, u1)))
    tint(ic, F.mask(ic, v1 - (v1 - v0) * 0.25, v1, u0, u1), m, (30, 20, 6), 0.25, 8)
    return m


def furrows(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, n: int = 7, soil=("#5e4430", "#34241a")) -> Image.Image:
    """Fresh ploughed land: ridges across the field, lit crest and dark trench, clods."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, soil[0], soil[1], (min(ys), max(ys)), noise=0.34, chroma=0.1)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(n):
        va = v0 + (v1 - v0) * k / n
        vb = v0 + (v1 - v0) * (k + 1) / n
        s = F.scale(vb)
        crest = [F.P(u, va + (vb - va) * 0.45) for u in np.linspace(u0, u1, 20)]
        crest = [(x, y + rnd.uniform(-2, 2)) for x, y in crest]
        trench = [F.P(u, vb) for u in np.linspace(u0, u1, 20)]
        d.polygon(crest + [(x, y - 3) for x, y in trench[::-1]], fill=(20, 12, 6, 120))
        d.line(crest, fill=(176, 142, 104, 150), width=int(7 * s), joint="curve")
        d.line([(x, y - 5 * s) for x, y in crest], fill=(210, 180, 140, 90), width=int(3 * s), joint="curve")
        for _ in range(int(26 * (u1 - u0))):
            u = rnd.uniform(u0, u1)
            x, y = F.P(u, va + (vb - va) * rnd.uniform(0.3, 0.7))
            r = rnd.uniform(4, 9) * s
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 20, 10, 140))
            d.ellipse((x - r * 0.8, y - r * 0.9, x + r * 0.4, y), fill=(170, 136, 98, 130))
    paste_clipped(ic, lay, m)
    return m


def hedge(ic: Icon, x0: float, x1: float, base: float, h: float, lumps: int = 14) -> Image.Image:
    """Hedgerow: a band of dark rounded shrub masses lit from the upper left."""
    rnd = ic.random
    m = blank()
    for k in range(lumps):
        x = x0 + (x1 - x0) * (k + rnd.uniform(0.1, 0.9)) / lumps
        r = h * rnd.uniform(0.45, 0.7)
        box = (x - r * 1.3, base - h * rnd.uniform(0.75, 1.0) - r * 0.3, x + r * 1.3, base + 6)
        bm = ic.mask("ellipse", box)
        ic.fill(bm, "#5a7a36", "#1c2c10", radial=(x - r * 0.8, box[1], r * 2.4), noise=0.3, chroma=0.12)
        m = union(m, bm)
    xs = (x0 - 40, x1 + 40)

    def dabs(d):
        for _ in range(int((x1 - x0) * 1.4)):
            x, y = rnd.uniform(*xs), rnd.uniform(base - h * 1.3, base)
            r = rnd.uniform(4, 8)
            col = (150, 176, 96, 80) if rnd.random() < 0.45 else (18, 30, 10, 90)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=col)

    ic.overlay(dabs, m)
    tint(ic, ic.mask("rectangle", (0, base - h * 0.35, SIZE, base + 10)), m, (10, 16, 4), 0.4, 10)
    return m

SEED = 41
REFS = ("farming_village", "fiber_crops_farm", "kings_manor", "noble_villa")

BRICK = ("#a0604a", "#5e3628")
SLATE = ("#747c86", "#383d46")
TILE = ("#a0664a", "#5a3224")
DRESSED = ("#d6ccb8", "#9a8e78")


def chimney(ic: Icon, x0, x1, top, bottom) -> None:
    m = ic.mask("rectangle", (x0, top, x1, bottom))
    bricks(ic, m, (x0, top, x1, bottom), BRICK[0], BRICK[1], 15, 26)
    ic.rect((x0 - 6, top - 8, x1 + 6, top + 6), "#9a8e7c", "#5e5448", edge=4)
    for cx in ((x0 + x1) / 2 - 12, (x0 + x1) / 2 + 12):
        ic.rect((cx - 7, top - 30, cx + 7, top - 8), "#b07a58", "#6a4230", edge=3)
    ic.shade(ic.mask("rectangle", ((x0 + x1) / 2 + 4, top, x1, bottom)), alpha=0.3)
    ic.outline([(x0, top), (x1, top), (x1, bottom), (x0, bottom)], 4)


def farmhouse(ic: Icon) -> None:
    L, R, EAVE, BASE = 220, 640, 400, 650
    chimney(ic, 262, 312, 190, 330)
    chimney(ic, 548, 598, 190, 330)
    wall = ic.mask("rectangle", (L, EAVE - 10, R, BASE))
    bricks(ic, wall, (L, EAVE - 10, R, BASE), BRICK[0], BRICK[1], 17, 40)
    # dressed stone plinth and string course
    ic.rect((L - 6, BASE - 30, R + 6, BASE), DRESSED[0], DRESSED[1], edge=4)
    ic.rect((L - 4, 512, R + 4, 526), DRESSED[0], DRESSED[1], edge=3)
    for x in (256, 344, 488, 576):
        ic.window(x, 430, x + 36, 486)
        ic.rect((x - 12, 488, x + 48, 498), DRESSED[0], DRESSED[1], edge=3)
    for x in (256, 344, 488, 576):
        ic.window(x, 548, x + 36, 604)
        ic.rect((x - 12, 606, x + 48, 616), DRESSED[0], DRESSED[1], edge=3)
    # central door with a pediment
    ic.rect((396, 548, 464, BASE - 30), DRESSED[0], DRESSED[1], edge=4)
    ic.door(408, 560, 452, BASE - 30, arched=False, surround=None)
    ic.poly([(386, 552), (474, 552), (430, 526)], DRESSED[0], DRESSED[1], edge=4)
    ic.window(412, 436, 448, 486)
    ic.shade(ic.mask("rectangle", (L, EAVE, R, EAVE + 40)), (20, 12, 4), 0.45, blur=10)
    ic.shade(ic.mask("rectangle", (560, EAVE, R, BASE)), alpha=0.18, blur=30)
    # hipped slate roof: front plane and the two hips
    front = [(L - 26, EAVE + 10), (R + 26, EAVE + 10), (R - 110, 270), (L + 110, 270)]
    shingles(ic, front, SLATE[0], SLATE[1], 22, 30)
    hipL = [(L - 26, EAVE + 10), (L + 110, 270), (L + 60, 270)]
    hipR = [(R + 26, EAVE + 10), (R - 110, 270), (R - 60, 270)]
    ic.shade(ic.poly_mask(hipR), (10, 12, 18), 0.3)
    ic.shade(ic.poly_mask(hipL), (230, 236, 246), 0.12)
    ic.line([(L + 110, 270), (L - 26, EAVE + 10)], 8, (150, 156, 166, 160))
    ic.line([(R - 110, 270), (R + 26, EAVE + 10)], 8, (60, 64, 72, 200))
    ic.line([(L + 110, 270), (R - 110, 270)], 12, (90, 96, 106))
    ic.rect((L - 30, EAVE + 6, R + 30, EAVE + 20), "#8e8272", "#5a5046", edge=4)  # cornice


def barn(ic: Icon) -> None:
    L, R, EAVE, BASE = 640, 950, 470, 660
    wall = ic.mask("rectangle", (L, EAVE - 10, R, BASE))
    bricks(ic, wall, (L, EAVE - 10, R, BASE), "#9a5c46", "#58342a", 17, 40)
    # arched cart door with dressed voussoirs
    ic.fill(ic.mask("ellipse", (730, 520, 860, 640)), DRESSED[0], DRESSED[1], (520, 600))
    ic.fill(ic.mask("rectangle", (730, 580, 860, BASE)), DRESSED[0], DRESSED[1], (580, BASE))
    ic.fill(ic.mask("ellipse", (746, 536, 844, 634)), "#2a1e16", "#120c08", (536, 634))
    ic.fill(ic.mask("rectangle", (746, 585, 844, BASE)), "#2a1e16", "#120c08", (585, BASE))
    planks(ic, (750, 600, 840, BASE), "#7a5a3a", "#3e2c1a", 22)
    for x in (676, 896):
        ic.rect((x - 12, 520, x + 12, 560), "#2a2420", "#141010", edge=4)  # ventilation slits
    ic.shade(ic.mask("rectangle", (L, EAVE, R, EAVE + 40)), (20, 12, 4), 0.45, blur=10)
    shingles(ic, [(L - 10, EAVE + 14), (R + 30, EAVE + 14), (R - 30, 360), (L + 10, 360)], TILE[0], TILE[1], 26, 34)
    ic.shade(ic.poly_mask([(R - 30, 360), (R + 30, EAVE + 14), (R - 70, EAVE + 14)]), (20, 10, 4), 0.3, blur=3)
    ic.line([(L + 10, 360), (R - 30, 360)], 12, (110, 64, 46))


def side_fence(ic: Icon, F: Field, u: float, posts: int = 6) -> None:
    """Post-and-rail fence of sawn timber along one side of the field, in perspective (taller in front)."""
    vs = np.linspace(0.0, 1.0, posts)
    feet = [F.P(u, v) for v in vs]
    tops = []
    for (x, y), v in zip(feet, vs):
        s = F.scale(v)
        tops.append((x, y - 110 * s))
    for f in (0.3, 0.72):  # two rails, lit on top
        line = [(x, y + (ty - y) * f) for (x, y), (_, ty) in zip(feet, tops)]
        for a, b, v in zip(line, line[1:], vs[1:]):
            timber(ic, a, b, max(11, 17 * F.scale(v)), "#a88c68", "#62503a")
    for (x, y), (tx, ty), v in zip(feet, tops, vs):
        s = F.scale(v)
        ic.shade(ic.mask("ellipse", (x - 20 * s, y - 6, x + 26 * s, y + 8)), alpha=0.35, blur=5)
        timber(ic, (x, y + 4), (tx, ty), max(14, 24 * s), "#a08462", "#5e4a34")
        ic.line([(tx - 7 * s, ty + 2), (tx + 7 * s, ty - 2)], 3, (220, 196, 160, 140))  # sawn top


def chest(ic: Icon, x0, y0, x1, y1, top: float = 40) -> None:
    """Iron-bound seed chest: dark oak body, lighter lid with a lit front edge, iron corner bands and hasp."""
    lid = [(x0 + 10, y0 - top), (x1 + 8, y0 - top), (x1, y0), (x0, y0)]
    lm = ic.poly_mask(lid)
    ic.fill(lm, "#b48a58", "#7a5632", (y0 - top, y0), noise=0.16)
    ic.overlay(lambda d: [d.line([(x0 + 8, y), (x1 + 6, y)], fill=(60, 38, 18, 90), width=3)
                          for y in np.linspace(y0 - top, y0, 4)[1:-1]], lm)
    front = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    m = ic.poly_mask(front)
    ic.fill(m, "#6e4a2c", "#2e1c0e", (y0, y1), noise=0.2)
    ic.overlay(lambda d: [d.line([(x0, y), (x1, y + ic.random.uniform(-2, 2))], fill=(24, 14, 6, 130), width=4)
                          for y in np.linspace(y0, y1, 4)[1:-1]], m)
    tint(ic, ic.mask("rectangle", (x0, y0, x1, y0 + 24)), m, (10, 6, 2), 0.45, 6)  # lid overhang shadow
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.3, y0, x1 + 20, y1)), m, (0, 0, 0), 0.25, 10)
    ic.line([(x0 - 2, y0 - 3), (x1 + 2, y0 - 3)], 9, (92, 62, 34))  # lid front edge
    ic.line([(x0, y0 - 6), (x1, y0 - 6)], 3, (240, 212, 164, 170))
    # iron bands at the corners, over the lid and down the front, with rivets
    for bx in (x0 + 4, x1 - 26):
        band = ic.mask("rectangle", (bx, y0 - 4, bx + 22, y1))
        ic.fill(band, "#6a6a70", "#2e2e34", (y0, y1), noise=0.1)
        ic.line([(bx + 3, y0), (bx + 3, y1)], 3, (190, 190, 196, 150))
        for ry in np.linspace(y0 + 14, y1 - 12, 3):
            ic.draw.ellipse((bx + 7, ry - 4, bx + 15, ry + 4), fill=(170, 170, 176, 255))
        lb = [(bx + 6 + 0.2 * (x1 - x0) * 0, y0 - top), (bx + 28, y0 - top), (bx + 22, y0), (bx, y0)]
        ic.fill(ic.poly_mask(lb), "#7a7a80", "#44444a", noise=0.1)
    cx = (x0 + x1) / 2
    ic.fill(ic.mask("rectangle", (cx - 14, y0 - 6, cx + 14, y0 + 36)), "#6a6a70", "#2e2e34")  # hasp
    ic.draw.ellipse((cx - 7, y0 + 16, cx + 7, y0 + 30), fill=(20, 18, 16, 255))
    ic.outline(lid + [(x0, y1), (x1, y1), (x1, y0)], 4, (30, 18, 10, 190))
    ic.outline(front, 4, (30, 18, 10, 190))


def ledger(ic: Icon, cx, cy, w, h) -> None:
    """A closed ledger lying flat on the lid: red-brown leather cover seen from above, pale page edge in front."""
    top = [(cx - w / 2 + 10, cy - h / 2), (cx + w / 2 + 6, cy - h / 2 + 4), (cx + w / 2 - 4, cy + h / 2),
           (cx - w / 2, cy + h / 2 - 4)]
    ic.shade(ic.poly_mask([(x + 8, y + 10) for x, y in top]), alpha=0.45, blur=5)
    pages = [top[3], top[2], (top[2][0], top[2][1] + 14), (top[3][0], top[3][1] + 14)]
    ic.poly(pages, "#f0e6cc", "#b4a484", edge=3)
    ic.overlay(lambda d: [d.line([(top[3][0] + 4, top[3][1] + k), (top[2][0] - 4, top[2][1] + k)],
                                 fill=(150, 130, 100, 110), width=1) for k in (5, 9)])
    ic.poly(top, "#98422a", "#4e1c10", edge=4)
    ic.line([(cx - w / 2 + 26, cy - h / 2 + 2), (cx - w / 2 + 18, cy + h / 2 - 2)], 8, (60, 22, 10))  # spine band
    ic.shade(ic.poly_mask(top), (255, 230, 200), 0.14, blur=6)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84

    barn(ic)
    farmhouse(ic)

    F = Field((150, 664), (900, 664), (18, 930), (1006, 930), persp=1.3)
    slab_face(ic, F, 66)
    soil(ic, F.band(0, 1, 0, 1), clods=80)
    # drilled rows running away from the viewer: straight ridges, identical bushes at even spacing
    rows = 7
    us = [(k + 0.5) / rows for k in range(rows)]

    def ridges(d):
        for u in us:
            d.line([F.P(u, 0), F.P(u, 1)], fill=(38, 26, 14, 150), width=26)
            d.line([F.P(u - 0.012, 0), F.P(u - 0.012, 1)], fill=(190, 160, 116, 70), width=6)

    ic.overlay(ridges, F.mask(ic))
    for v in (0.02, 0.2, 0.42, 0.68, 0.99):
        s = F.scale(v)
        for u in us:
            x, y = F.P(u, v)
            front = v > 0.9
            pulse_bush(ic, x, y + 4, (160 if front else 150) * s * rnd.uniform(0.96, 1.04),
                       (150 if front else 130) * s * rnd.uniform(0.96, 1.04),
                       pods=0 if v < 0.3 else (2 if v < 0.8 else 3), flowers=1 if rnd.random() < 0.2 else 0,
                       leaflet=11, pod_scale=1.15)
    # the rail fence along the left edge of the field, in front of the first row of bushes
    side_fence(ic, F, -0.012, 6)

    # seed store, bottom right: the iron-bound seed chest in front with the ledger on its lid,
    # an open sack of beans beside it and one tied sack behind
    ic.shade(ic.mask("ellipse", (640, 950, 1018, 1008)), alpha=0.5, blur=10)
    sack(ic, 952, 870, 110, 150, ("#b89e72", "#5a462c"))
    bean_sack(ic, 700, 1004, 150, 170, weights=(2, 3, 2, 3, 1), bean=12)
    chest(ic, 786, 880, 1010, 1004, 46)
    ledger(ic, 890, 852, 130, 50)
