"""Legume Farmstead (tier 1 of the legume farm chain): a timber-framed farmhouse with a fodder byre,
rows of peas and beans in front, sealed seed jars and a sack of beans.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/legume_farmstead/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/legume_farmstead

Identity: the pulse bushes hung with pods (shared with the whole chain) grown by a larger holding
than the Legume Farm: a half-timbered farmhouse on a stone plinth and an open byre stacked with
fodder, tying the pulses to the livestock (the building's fodder leys); sealed seed jars and an
open sack of beans at the bottom right keep next year's sowing.

Local helpers shared by the legume family: ``pulse_bush``, ``pod``, ``beans`` / ``bean_heap_items``,
``bean_sack``, ``soil``; generic ones copied from cookshop / tavern / victualling_yard.
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

SEED = 17
REFS = ("farming_village", "fiber_crops_farm", "sheep_farms", "free_village")


def farmhouse(ic: Icon) -> None:
    rnd = ic.random
    L, R, EAVE, BASE = 90, 520, 470, 800
    # stone plinth, plaster panels, oak frame
    stones(ic, (L, BASE - 70, R, BASE), "#a0968a", "#6e665a", 30)
    wall = ic.mask("rectangle", (L, EAVE - 20, R, BASE - 70))
    ic.fill(wall, "#dccaa4", "#a8946e", (EAVE, BASE), noise=0.2, chroma=0.06)
    for _ in range(10):
        x, y = rnd.uniform(L, R), rnd.uniform(EAVE, BASE - 70)
        r = rnd.uniform(20, 46)
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.7, x + r * 1.4, y + r * 0.7)), wall,
             rnd.choice([(80, 64, 40), (255, 244, 220)]), rnd.uniform(0.08, 0.16), 14)
    posts = (L + 12, 196, 300, 404, R - 12)
    rail = 610
    for x in posts:
        timber(ic, (x, EAVE - 14), (x + rnd.uniform(-2, 2), BASE - 70), 22)
    timber(ic, (L, rail), (R, rail + 3), 20)
    for x0, x1, up in ((L + 12, 196, True), (404, R - 12, False)):
        timber(ic, (x0, rail if up else EAVE), (x1, EAVE if up else rail), 16)
    timber(ic, (L - 6, BASE - 72), (R + 6, BASE - 70), 22)
    ic.door(318, 626, 390, BASE - 74, arched=False, surround=None)
    for x in (130, 222):
        ic.window(x, 520, x + 44, 568)
    ic.window(440, 648, 480, 690)
    tint(ic, ic.mask("rectangle", (L, BASE - 130, R, BASE)), None, (40, 34, 20), 0.2, 20)
    # thatch, gabled at the left (a hipped gablet), ridge running right
    roof = [(L - 56, EAVE + 24), (R + 52, EAVE + 26), (R - 24, 232), (L + 60, 228)]
    thatch(ic, roof, "#c4953e", "#5a3c14", 40)
    hipR = [(R - 24, 232), (R + 52, EAVE + 26), (R - 30, EAVE + 26)]
    ic.shade(ic.poly_mask(hipR), (20, 12, 4), 0.32, blur=3)
    hipL = [(L + 60, 228), (L - 56, EAVE + 24), (L + 30, EAVE + 24)]
    ic.shade(ic.poly_mask(hipL), (255, 236, 196), 0.14, blur=3)
    ic.shade(ic.mask("rectangle", (L, EAVE + 20, R, EAVE + 80)), (20, 12, 4), 0.5, blur=12)
    ic.shade(ic.mask("rectangle", (L, EAVE + 40, R, EAVE + 62)), (16, 8, 2), 0.7, blur=3)
    eave = [(x, EAVE + 24 + rnd.uniform(-4, 6)) for x in np.linspace(L - 56, R + 52, 20)]
    lip = eave + [(x, y + 20 + rnd.uniform(-3, 4)) for x, y in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7446", "#4a3a1e", noise=0.35)
    ic.outline(roof, 6)
    ic.line([(L + 60, 228), (R - 24, 232)], 18, (110, 92, 58))
    # brick chimney through the thatch
    cm = ic.mask("rectangle", (398, 150, 446, 260))
    bricks(ic, cm, (398, 150, 446, 260), "#9a6a50", "#5e3e2c", 16, 26)
    ic.rect((392, 142, 452, 158), "#8e7c6a", "#5a4c40", edge=4)
    ic.outline([(398, 150), (446, 150), (446, 260), (398, 260)], 4)
    ic.shade(ic.mask("rectangle", (424, 150, 446, 260)), alpha=0.3)


def ox(ic: Icon, cx: float, top: float, clip: Image.Image) -> None:
    """Head and shoulders of a red-brown ox looking out of the byre: shoulders in shadow, pale muzzle,
    short pale horns, a white blaze; everything clipped to the byre opening."""
    with ic.clipped(clip):
        # shoulders and neck, mostly in the byre's shadow
        sh = ic.mask("ellipse", (cx - 120, top + 70, cx + 110, top + 300))
        ic.fill(sh, "#8a5436", "#2a180e", radial=(cx - 60, top + 90, 220), noise=0.2)
        ic.shade(ic.mask("rectangle", (cx + 10, top + 60, cx + 140, top + 300)), (10, 6, 2), 0.4, blur=24)
    head = [(cx - 40, top + 22), (cx - 10, top + 12), (cx + 22, top + 14), (cx + 44, top + 28), (cx + 38, top + 84),
            (cx + 30, top + 118), (cx - 30, top + 118), (cx - 38, top + 84)]
    hm = ic.poly_mask(head)
    # ears first (behind the head)
    for sgn in (-1, 1):
        ex = cx + sgn * 44
        ear = [(ex, top + 30), (ex + sgn * 40, top + 26), (ex + sgn * 46, top + 40), (ex + sgn * 8, top + 50)]
        ic.poly(ear, "#9a6040" if sgn < 0 else "#6a3e26", "#4a2a18", edge=3)
    ic.fill(hm, "#a8683e", "#5a3018", radial=(cx - 20, top + 30, 110), noise=0.16)
    ic.shade(ic.poly_mask([(cx + 6, top + 12), (cx + 44, top + 28), (cx + 38, top + 84), (cx + 30, top + 118), (cx + 6, top + 118)]),
             (20, 10, 4), 0.35, blur=4)
    blaze = [(cx - 12, top + 18), (cx + 8, top + 16), (cx + 4, top + 50), (cx - 2, top + 62), (cx - 8, top + 50)]
    ic.fill(ic.poly_mask(blaze), "#e4d8c4", "#b8a88e", noise=0.1)
    muz = ic.mask("ellipse", (cx - 34, top + 82, cx + 34, top + 126))
    ic.fill(muz, "#c4a48c", "#7a5e4c", (top + 82, top + 126), noise=0.12)
    for sgn in (-1, 1):
        ic.draw.ellipse((cx + sgn * 14 - 5, top + 104, cx + sgn * 14 + 5, top + 112), fill=(40, 24, 18, 255))
        ic.draw.ellipse((cx + sgn * 26 - 6, top + 50, cx + sgn * 26 + 6, top + 60), fill=(20, 12, 8, 255))
    ic.line([(cx - 28, top + 52), (cx - 24, top + 51)], 3, (255, 240, 220, 150))  # eye glint
    ic.outline(head, 4, (40, 22, 12, 200))
    # short horns curving up and out
    for sgn in (-1, 1):
        pts = [(cx + sgn * 26, top + 20), (cx + sgn * 50, top + 10), (cx + sgn * 64, top - 8), (cx + sgn * 62, top - 22)]
        ic.line(pts, 12, (60, 46, 30))
        ic.line(pts, 8, (222, 206, 172))
        ic.line(pts[:2], 4, (255, 246, 220, 150))


def byre(ic: Icon) -> None:
    rnd = ic.random
    L, R, EAVE, BASE, RIDGE = 520, 900, 592, 810, 470
    opening = ic.mask("rectangle", (L, EAVE, R, BASE))
    ic.rect((L, EAVE, R, BASE), "#2e2218", "#150f0a", edge=0)  # dark open interior
    # a stacked hay rick in the right bay: courses of straw, a lit top edge
    rick = [(712, BASE), (714, 720), (730, 690), (770, 670), (830, 664), (872, 676), (888, 700), (890, BASE)]
    hm = hay(ic, rick, 300)
    courses = blank()
    cd = ImageDraw.Draw(courses)
    for y in (716, 752, 786):
        cd.line([(700, y + rnd.uniform(-4, 4)), (900, y + rnd.uniform(-4, 4))], fill=255, width=7)
    tint(ic, courses, hm, (40, 24, 6), 0.45, 3)
    ic.line(rick[1:-1], 8, (240, 214, 140, 170))  # lit top of the rick
    ic.shade(ic.mask("rectangle", (L, EAVE, R, 690)), alpha=0.45, blur=20)
    # an ox looking out of the left bay
    ox(ic, 612, 640, opening)
    for x in (L + 10, 700, R - 10):
        timber(ic, (x, EAVE - 6), (x + rnd.uniform(-3, 3), BASE), 24)
    timber(ic, (L, EAVE + 12), (R, EAVE + 14), 20)
    # low roof of weathered grey-brown shingles, well below the house ridge
    roof = [(L - 20, EAVE + 26), (R + 44, EAVE + 30), (R - 16, RIDGE + 4), (L + 20, RIDGE)]
    rm = shingles(ic, roof, "#8c806c", "#453c30", course=28, stagger=38, edge=6)
    for _ in range(8):
        x, y = rnd.uniform(L, R), rnd.uniform(RIDGE, EAVE + 20)
        r = rnd.uniform(24, 60)
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.5, x + r * 1.4, y + r * 0.5)), rm,
             rnd.choice([(84, 92, 58), (30, 24, 18), (200, 190, 170)]), rnd.uniform(0.1, 0.22), 14)
    ic.shade(ic.poly_mask([(R - 16, RIDGE + 4), (R + 44, EAVE + 30), (R - 50, EAVE + 30)]), (20, 12, 4), 0.3, blur=3)
    # shadow thrown on the byre roof by the house where the two roofs meet
    tint(ic, ic.poly_mask([(540, RIDGE - 10), (640, RIDGE - 10), (660, EAVE + 40), (560, EAVE + 40)]), rm, (12, 8, 4), 0.55, 14)
    ic.shade(ic.mask("rectangle", (L, EAVE + 20, R, EAVE + 70)), (20, 12, 4), 0.45, blur=12)
    ic.line([(L + 20, RIDGE), (R - 16, RIDGE + 4)], 14, (74, 64, 52))


def staked_bush(ic: Icon, x: float, base: float, w: float, h: float, pods: int = 3) -> None:
    """Climbing beans up a pole: the pole stands behind a tall narrow bush and shows above it."""
    lean = ic.random.uniform(-14, 14)
    tip = (x + lean, base - h - 96)
    timber(ic, (x + lean * 0.2, base - 10), tip, 15, "#a88a62", "#5a4430")
    pulse_bush(ic, x, base, w, h, pods=pods, flowers=2, leaflet=11)
    # the vine climbing on above the bush: a few leaflets up the pole
    for k in range(3):
        f = 0.25 + 0.22 * k
        px, py = x + lean * (0.2 + 0.8 * (h + 96 * f) / (h + 96)), base - h - 96 * f + 10
        ic.fill(ic.mask("ellipse", (px - 16 + 10 * (k % 2), py - 10, px + 6 + 10 * (k % 2), py + 6)),
                PEA_LEAF[1], PEA_LEAF[0], noise=0.2)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84

    byre(ic)
    farmhouse(ic)

    # the field in front of the house: a back row of beans climbing poles (a gap left at the door),
    # then a front row of big pulse bushes
    ground = [(20, 800), (760, 806), (780, 1000), (14, 1000)]
    soil(ic, ground, furrows=[[(30, y), (770, y + 2)] for y in (870, 940)])
    for x in (70, 180, 452, 560, 668):
        staked_bush(ic, x + rnd.uniform(-8, 8), 880 + rnd.uniform(-4, 4), 108 * rnd.uniform(0.92, 1.08),
                    150 * rnd.uniform(0.94, 1.06), pods=3)
    for x in (130, 360, 590):
        pulse_bush(ic, x + rnd.uniform(-10, 10), 992 + rnd.uniform(-4, 4), 232 * rnd.uniform(0.92, 1.08),
                   192 * rnd.uniform(0.92, 1.08), pods=5, flowers=2)
    ic.shade(ic.mask("rectangle", (0, 975, 800, 1024)), (10, 18, 4), alpha=0.3, blur=16)

    # seed store, bottom right: two glazed red-brown seed jars sealed with dark wax cloth, an open sack of beans
    ic.shade(ic.mask("ellipse", (700, 950, 1016, 1004)), alpha=0.45, blur=10)
    jars = ((772, 994, 150, 188, ("#b4643a", "#4e2412")), (882, 998, 118, 150, ("#b8843e", "#553414")))
    for cx, base, w, h, body in jars:
        crock(ic, cx, base, w, h, body, ("#5a3a2a", "#1e120a"))
        # glaze: a sharp glossy highlight and a darker drip line near the foot
        ic.line([(cx - w * 0.3, base - h * 0.62), (cx - w * 0.33, base - h * 0.4)], 6, (255, 236, 210, 150))
        ic.line([(cx - w * 0.46, base - h * 0.22), (cx + w * 0.46, base - h * 0.2)], 4, (60, 24, 10, 110))
    bean_sack(ic, 966, 1000, 118, 140, weights=(2, 3, 2, 3, 1), bean=11)
