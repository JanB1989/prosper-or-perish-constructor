"""Transport Office (transport_office): a town freight office with its cart gate, carts and crates.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/transport_office/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/transport_office

Identity: an urban stone-and-plaster office under a blue-grey slate roof, a wide arched cart gate
with crates inside, a loaded dray cart and a porter's handcart of sacks on the cobbles, and a
hanging sign with a cartwheel. Stone, slate and open carts keep it apart from the Carrier Inn
(tiled roof, covered wagon, packhorse on an earth road).
Transport-family helpers copied from carrier_inn (``union``, ``tint``, ``paste_clipped``, ``rim``,
``stones``, ``shingles``, ``timber``, ``planks``, ``hboards``, ``wheel``, ``cask``, ``sack``,
``rope``), ``crate`` from the victualling yard; local: ``office``, ``dray``, ``handcart``, ``sign``,
``street``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 5
REFS = ("trade_office", "counting_house", "customs_house", "market_warehouse")

BASE = 880
GROUND = 932
L, R = 110, 830
EAVE, RIDGE, BAND = 382, 184, 624
ACX, ARW, ASP = 500, 104, 764  # cart gate
IRON = (40, 38, 36)


# ---------------------------------------------------------------- transport-family helpers
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
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def rim(ic: Icon, m: Image.Image, width: int = 4, color=(40, 24, 12), alpha: float = 0.75) -> None:
    """Soft dark edge just inside a mask (a form's contour without a hard outline)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(2 * width + 1)))
    ic.shade(ring, color, alpha, blur=1)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
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
    paste_clipped(ic, lay, m)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, soft course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
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
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    if edge:
        ic.outline(pts, edge)
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
    (x0, y0), (x1, y1) = p0, p1
    ln = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
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


def planks(ic: Icon, pts, c1="#86603e", c2="#4e3522", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    rnd = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * rnd.uniform(0.8, 1.2)
        t = rnd.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + rnd.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + rnd.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def hboards(ic: Icon, pts, c1="#8a6442", c2="#4e3522", board: float = 24) -> Image.Image:
    """Horizontal boards (cart sides, hull strakes): per-board tone, lit top edge, dark joint below."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    rnd = ic.random.uniform
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = min(ys)
    while y < max(ys):
        h = board * rnd(0.85, 1.15)
        t = rnd(-1, 1)
        d.rectangle((min(xs), y, max(xs), y + h), fill=(255, 225, 180, int(26 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(3):
            gx = rnd(min(xs), max(xs))
            gy = y + rnd(4, h - 4)
            d.line([(gx, gy), (gx + rnd(40, 120), gy + rnd(-2, 2))], fill=(40, 24, 12, 60), width=2)
        d.line([(min(xs), y + 2), (max(xs), y + 2)], fill=(255, 230, 190, 50), width=3)
        d.line([(min(xs), y + h), (max(xs), y + h)], fill=(30, 18, 10, 150), width=4)
        y += h
    paste_clipped(ic, lay, m)
    return m


def wheel(ic: Icon, cx, cy, r, spokes: int = 10, tone: float = 1.0) -> None:
    """Spoked cart wheel seen from the side: felloes lit top-left, iron tyre, turned hub."""
    k = lambda c: tuple(int(v * tone) for v in c)  # noqa: E731
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78)))
    sw = max(7, int(r * 0.1))
    for i in range(spokes):
        a = 2 * math.pi * i / spokes + 0.25
        p0 = (cx + math.cos(a) * r * 0.16, cy + math.sin(a) * r * 0.16)
        p1 = (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82)
        ic.line([p0, p1], sw + 4, k((46, 30, 18)))
        lit = 0.5 + 0.5 * math.cos(a + 2.4)  # spokes facing the upper left catch the light
        ic.line([p0, p1], sw, k(tuple(int(80 + 70 * lit + c) for c in (20, 0, -26))))
    ic.fill(ring, k((156, 112, 70)), k((58, 38, 22)), radial=(cx - r * 0.6, cy - r * 0.7, r * 2.1), noise=0.16)
    for i in range(spokes // 2):  # felloe joints
        a = 2 * math.pi * i / (spokes // 2) + 0.6
        ic.line([(cx + math.cos(a) * r * 0.78, cy + math.sin(a) * r * 0.78), (cx + math.cos(a) * r * 0.95,
                 cy + math.sin(a) * r * 0.95)], 3, (40, 26, 14, 160))
    tw = max(6, int(r * 0.09))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=k((52, 50, 50)) + (255,), width=tw))
    ic.overlay(lambda d: d.arc((cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2), 185, 265, fill=(200, 192, 182, 130),
                               width=3))
    hr = r * 0.2
    ic.fill(ic.mask("ellipse", (cx - hr, cy - hr, cx + hr, cy + hr)), k((150, 108, 66)), k((50, 32, 18)),
            radial=(cx - hr * 0.5, cy - hr * 0.6, hr * 2), noise=0.12)
    ic.overlay(lambda d: d.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), outline=(52, 50, 50, 255), width=5))
    ic.draw.ellipse((cx - hr * 0.35, cy - hr * 0.35, cx + hr * 0.35, cy + hr * 0.35), fill=(36, 32, 30, 255))
    whole = ic.mask("ellipse", (cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2))
    tint(ic, ic.mask("ellipse", (cx - r * 0.2, cy - r * 0.1, cx + r * 1.6, cy + r * 1.6)), whole, (10, 4, 0), 0.3, r * 0.2)


def cask(ic: Icon, x0, y0, x1, y1, wood=("#a4764c", "#4c3120"), hoops=(0.14, 0.34, 0.66, 0.86)) -> Image.Image:
    """Standing coopered cask: bulged staves shaded as a cylinder, iron hoops, lit head on top."""
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    bul = w * 0.09
    lip = max(h * 0.07, w * 0.13)
    ts = np.linspace(0, 1, 32)
    left = [(x0 - bul * math.sin(math.pi * t), y0 + h * t) for t in ts]
    right = [(x1 + bul * math.sin(math.pi * t), y0 + h * t) for t in ts[::-1]]
    bottom = [(cx + math.cos(a) * w / 2, y1 + math.sin(a) * lip) for a in np.linspace(0, math.pi, 16)]
    pts = left + [(x0, y1)] + bottom[::-1] + [(x1, y1)] + right
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], radial=(x0 + w * 0.3, y0 + h * 0.35, w * 1.05), noise=0.16)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.62, y0 - 10, x1 + bul + 10, y1 + lip + 10)), m, (16, 8, 4), 0.35, 14)
    for f in hoops:
        y = y0 + h * f
        b = bul * math.sin(math.pi * f)
        arc = [(cx + math.cos(a) * (w / 2 + b), y + math.sin(a) * lip * 0.9) for a in np.linspace(0, math.pi, 18)]
        ic.line(arc, 9, (58, 54, 52))
    head = (x0 - 1, y0 - lip, x1 + 1, y0 + lip)
    ic.fill(ic.mask("ellipse", head), "#7e5a3a", "#4a3220", (y0 - lip, y0 + lip), noise=0.12)
    inner = (x0 + 7, y0 - lip * 0.7, x1 - 7, y0 + lip * 0.7)
    ic.fill(ic.mask("ellipse", inner), "#d8b484", "#9a7448", radial=(x0 + w * 0.3, y0 - lip, w * 0.9), noise=0.14)
    # sunlit chime: the head's front rim catches the light and lifts the cask off the load behind it
    ic.overlay(lambda d: d.arc(head, 10, 170, fill=(236, 212, 168, 230), width=6))
    ic.overlay(lambda d: d.arc(head, 190, 290, fill=(236, 212, 168, 150), width=4))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
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
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.28, cx + w, base + 10)), body, (24, 14, 6), 0.4, 10)  # underside
    for _ in range(5):  # hessian weave and creases
        yy = base - h * ic.random.uniform(0.2, 0.75)
        ic.line([(cx - w * 0.35, yy), (cx + w * 0.3, yy + ic.random.uniform(-6, 6))], 2, (60, 44, 26, 70))
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.14, base - h * 0.8), (nx - w * 0.1, base - h * 1.02), (nx - w * 0.2, base - h * 1.12),
            (nx + w * 0.02, base - h * 1.08), (nx + w * 0.2, base - h * 1.14), (nx + w * 0.12, base - h * 1.0),
            (nx + w * 0.15, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.13, base - h * 0.96), (nx + w * 0.13, base - h * 0.95)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))


def rope(ic: Icon, pts, width: int = 6) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, (176, 146, 100))


def crate(ic: Icon, x0, y0, x1, y1, top: float = 26, c=("#8e6a46", "#4e3420")) -> None:
    """Sealed crate: lit lid seen from above, boarded front with corner battens, darker right end."""
    lid = [(x0 + 6, y0 - top), (x1 + 4, y0 - top), (x1, y0), (x0, y0)]
    ic.fill(ic.poly_mask(lid), "#b48e62", "#7e5e3c", (y0 - top, y0), noise=0.18)
    ic.overlay(lambda d: [d.line([(x0 + 4, y0 - top * f), (x1 + 2, y0 - top * f)], fill=(70, 46, 26, 110), width=3)
                          for f in (0.35, 0.7)])
    front = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    m = ic.poly_mask(front)
    ic.fill(m, c[0], c[1], (y0, y1), noise=0.2)
    ic.overlay(lambda d: [d.line([(x0, y), (x1, y + ic.random.uniform(-2, 2))], fill=(40, 24, 12, 120), width=3)
                          for y in np.linspace(y0, y1, 4)[1:-1]], m)
    for bx in (x0 + 10, x1 - 10):
        timber(ic, (bx, y0 + 2), (bx, y1 - 2), 16, "#8a6440", "#4e3522")
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.3, y0, x1 + 20, y1)), m, (0, 0, 0), 0.25, 10)
    ic.outline(lid + [(x0, y1), (x1, y1), (x1, y0)], 4, (40, 26, 16, 170))
    ic.outline(front, 4, (40, 26, 16, 170))


# ---------------------------------------------------------------- the office
def chimney(ic: Icon, x0, x1, top, bottom) -> None:
    cm = ic.mask("rectangle", (x0, top, x1, bottom))
    stones(ic, (x0, top, x1, bottom), "#b0a492", "#6e6456", course=24)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, top, x1 + 10, bottom)), cm, (0, 0, 0), 0.32, 10)
    ic.outline([(x0, top), (x1, top), (x1, bottom), (x0, bottom)], 4)
    ic.poly([(x0 - 10, top - 12), (x1 + 10, top - 12), (x1 + 10, top + 8), (x0 - 10, top + 8)], "#bcb09c", "#7c7264",
            edge=4)


def dormer(ic: Icon, rm, x0, x1, y0, y1) -> None:
    cx = (x0 + x1) / 2
    ic.fill(ic.mask("rectangle", (x0, y0 + 34, x1, y1)), "#d4ccbc", "#948a7a", noise=0.16)
    ic.window(x0 + 20, y0 + 50, x1 - 20, y1 - 12)
    shingles(ic, [(x0 - 22, y0 + 44), (cx, y0 - 16), (x1 + 22, y0 + 44), (x1 + 22, y0 + 60), (cx, y0 + 6),
                  (x0 - 22, y0 + 60)], "#7a90a8", "#303c4c", course=14, stagger=20, edge=5)
    tint(ic, ic.mask("rectangle", (x0 - 20, y1, x1 + 40, y1 + 24)), rm, (0, 0, 0), 0.35, 8)
    ic.outline([(x0, y0 + 44), (x1, y0 + 44), (x1, y1), (x0, y1)], 4)


def office(ic: Icon) -> None:
    chimney(ic, 190, 246, 118, RIDGE + 40)
    chimney(ic, 690, 744, 126, RIDGE + 40)
    # hipped slate roof
    roof = [(L - 34, EAVE + 12), (L + 112, RIDGE), (R - 112, RIDGE + 2), (R + 34, EAVE + 12)]
    rm = shingles(ic, roof, "#7a90a8", "#303c4c", course=22, stagger=30, edge=0)
    tint(ic, ic.poly_mask([(L - 40, EAVE + 12), (L + 112, RIDGE), (L + 200, RIDGE), (L + 80, EAVE + 12)]), rm,
         (255, 244, 226), 0.12, 20)
    tint(ic, ic.poly_mask([(R - 112, RIDGE), (R + 40, EAVE + 12), (R - 60, EAVE + 12), (R - 160, RIDGE)]), rm,
         (0, 0, 0), 0.25, 20)
    tint(ic, ic.mask("rectangle", (L - 40, EAVE - 40, R + 40, EAVE + 14)), rm, (10, 10, 14), 0.3, 12)
    for x0, x1 in ((190, 246), (690, 744)):
        tint(ic, ic.poly_mask([(x1, RIDGE + 20), (x1 + 40, RIDGE + 40), (x1 + 40, RIDGE + 90), (x1, RIDGE + 70)]), rm,
             (0, 0, 0), 0.3, 10)
    ic.line([(L + 112, RIDGE), (R - 112, RIDGE + 2)], 12, (70, 76, 84))
    ic.outline(roof, 6)
    dormer(ic, rm, 264, 346, 228, 330)
    dormer(ic, rm, 588, 670, 230, 332)

    # upper floor: limewashed plaster, stone surrounds, grey-green shutters
    up = ic.mask("rectangle", (L, EAVE + 12, R, BAND))
    ic.fill(up, "#e2cc9e", "#b08e5e", (EAVE, BAND), noise=0.2, chroma=0.05)
    for _ in range(14):
        x, y = ic.random.uniform(L, R), ic.random.uniform(EAVE, BAND)
        r = ic.random.uniform(30, 70)
        tint(ic, ic.mask("ellipse", (x - r * 1.3, y - r * 0.7, x + r * 1.3, y + r * 0.7)), up,
             ic.random.choice([(70, 60, 40), (255, 250, 236), (90, 90, 70)]), ic.random.uniform(0.06, 0.14), 16)
    for cx in (176, 326, 476, 626, 776):
        x0, x1, y0, y1 = cx - 30, cx + 30, 446, 548
        ic.rect((x0 - 18, y0 - 18, x1 + 18, y1 + 20), "#c4b8a2", "#8e8472", edge=4)
        ic.window(x0, y0, x1, y1)
        for sx in (-1, 1):
            sh = (x0 - 60, y0 - 12, x0 - 22, y1 + 12) if sx < 0 else (x1 + 22, y0 - 12, x1 + 60, y1 + 12)
            ic.rect(sh, "#5e8468", "#2e4a36", edge=4)
            ic.line([(sh[0] + 4, (sh[1] + sh[3]) / 2), (sh[2] - 4, (sh[1] + sh[3]) / 2)], 4, (40, 50, 40, 160))
        tint(ic, ic.mask("rectangle", (x0 - 20, y1 + 20, x1 + 30, y1 + 40)), up, (0, 0, 0), 0.25, 6)
    tint(ic, ic.mask("rectangle", (L, EAVE + 12, R, EAVE + 70)), up, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (R - 160, EAVE, R, BAND)), up, (0, 0, 0), 0.15, 40)
    ic.outline([(L, EAVE + 12), (R, EAVE + 12), (R, BAND), (L, BAND)], 5)

    # ground floor: rusticated ashlar
    wall = ic.mask("rectangle", (L, BAND, R, BASE))
    stones(ic, (L, BAND, R, BASE), "#bca47e", "#7a6448", course=40, moss=0.05)
    tint(ic, ic.mask("rectangle", (L, BASE - 80, R, BASE)), wall, (40, 44, 20), 0.2, 22)
    tint(ic, ic.mask("rectangle", (L, BAND, R, BAND + 40)), wall, (0, 0, 0), 0.35, 10)
    tint(ic, ic.mask("rectangle", (R - 160, BAND, R, BASE)), wall, (0, 0, 0), 0.18, 40)
    ic.rect((L - 14, BAND - 10, R + 14, BAND + 12), "#c8bca6", "#8a806e", edge=4)  # string course
    ic.outline([(L, BAND), (R, BAND), (R, BASE), (L, BASE)], 5)
    # office door up two steps, between the dray and the cart gate, under a stone hood
    dx0, dx1 = 294, 356
    ic.rect((dx0 - 16, 684, dx1 + 16, 700), "#d0c4ae", "#948a76", edge=4)
    ic.door(dx0, 700, dx1, BASE - 34)
    tint(ic, ic.mask("rectangle", (dx0, 700, dx1, 730)), None, (0, 0, 0), 0.3, 6)
    ic.rect((dx0 - 10, BASE - 34, dx1 + 10, BASE - 17), "#dcd0b8", "#a49882", edge=4)  # sunlit steps
    ic.rect((dx0 - 22, BASE - 17, dx1 + 20, BASE), "#cabea6", "#8e8470", edge=4)
    ic.line([(dx0 - 8, BASE - 31), (dx1 + 8, BASE - 31)], 3, (255, 246, 226, 120))
    ic.line([(dx0 - 20, BASE - 14), (dx1 + 18, BASE - 14)], 3, (255, 246, 226, 110))
    # barred windows right of the gate
    for x0, x1 in ((664, 716), (756, 804)):
        ic.rect((x0 - 12, 690, x1 + 12, 790), "#c4b8a2", "#8e8472", edge=4)
        ic.rect((x0, 702, x1, 778), "#2c2a2a", "#161414", noise=0.06, edge=0)
        for f in (0.33, 0.66):
            ic.line([(x0 + (x1 - x0) * f, 702), (x0 + (x1 - x0) * f, 778)], 5, (70, 66, 62))
        tint(ic, ic.mask("rectangle", (x0 - 12, 790, x1 + 20, 812)), wall, (0, 0, 0), 0.3, 6)

    # arched cart gate, crates stacked in the dark
    vr = ARW + 30
    ring = union(ic.mask("ellipse", (ACX - vr, ASP - vr, ACX + vr, ASP + vr)),
                 ic.mask("rectangle", (ACX - vr, ASP, ACX + vr, BASE)))
    ic.fill(ring, "#c8bca6", "#8a806e", (ASP - vr, BASE), noise=0.16)
    for a in np.linspace(math.pi, 2 * math.pi, 9):
        ic.line([(ACX + math.cos(a) * ARW, ASP + math.sin(a) * ARW), (ACX + math.cos(a) * vr, ASP + math.sin(a) * vr)],
                4, (60, 50, 40, 170))
    ic.poly([(ACX - 16, ASP - vr - 6), (ACX + 16, ASP - vr - 6), (ACX + 12, ASP - ARW + 4), (ACX - 12, ASP - ARW + 4)],
            "#d6cab2", "#968a76", edge=4)  # keystone
    opening = union(ic.mask("ellipse", (ACX - ARW, ASP - ARW, ACX + ARW, ASP + ARW)),
                    ic.mask("rectangle", (ACX - ARW, ASP, ACX + ARW, BASE)))
    ic.fill(opening, "#2a2018", "#100c08", (ASP - ARW, BASE), noise=0.1)
    with ic.clipped(opening):
        crate(ic, ACX - 90, 800, ACX - 6, BASE, top=18, c=("#6a5038", "#34261a"))
        crate(ic, ACX - 70, 736, ACX - 10, 782, top=16, c=("#5e4632", "#30221a"))
        sack(ic, ACX + 50, BASE, 70, 80, c=("#8a8070", "#3e382e"))
        tint(ic, opening, None, (0, 0, 0), 0.35)
        tint(ic, ic.mask("rectangle", (ACX - ARW, ASP - ARW, ACX + ARW, ASP + 20)), None, (0, 0, 0), 0.55, 24)
        for sx in (-1, 1):
            x0, x1 = ACX + sx * ARW, ACX + sx * (ARW - 34)
            leaf = [(x0, ASP - 50), (x1, ASP - 26), (x1, BASE - 20), (x0, BASE)]
            planks(ic, leaf, "#6a4e34", "#38281a", board=14)
            tint(ic, ic.poly_mask(leaf), None, (0, 0, 0), 0.2)
    ic.overlay(lambda d: d.arc((ACX - vr, ASP - vr, ACX + vr, ASP + vr), 180, 360, fill=(40, 30, 22, 200), width=5))


def sign(ic: Icon) -> None:
    """Short iron bracket off the right corner with a hanging board painted with a cartwheel."""
    by = 598
    ic.line([(R - 30, by), (904, by)], 14, IRON)
    ic.line([(R - 30, by + 62), (866, by + 4)], 10, IRON)
    ic.draw.arc((892, by - 14, 916, by + 10), 90, 360, fill=IRON + (255,), width=7)
    x0, x1, y0, y1 = 812, 902, 636, 726
    for x in (x0 + 16, x1 - 16):
        ic.line([(x, by + 6), (x, y0)], 4, (70, 66, 60))
    board = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    ic.fill(ic.poly_mask(board), "#4e6a5a", "#263a30", (y0, y1), noise=0.14)
    ic.rect((x0 - 6, y0 - 6, x1 + 6, y0 + 6), "#8a6440", "#4e3522", edge=3)
    ic.rect((x0 - 6, y1 - 6, x1 + 6, y1 + 6), "#8a6440", "#4e3522", edge=3)
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2 + 2, 28
    for i in range(8):
        a = i * math.pi / 4
        ic.line([(cx, cy), (cx + math.cos(a) * r, cy + math.sin(a) * r)], 5, (214, 190, 120))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(214, 190, 120, 255), width=7))
    ic.draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=(214, 190, 120, 255))
    tint(ic, ic.mask("rectangle", (x0 + 60, y0, x1, y1)), ic.poly_mask(board), (0, 0, 0), 0.25, 14)
    ic.outline(board, 4)


# ---------------------------------------------------------------- carts
def dray(ic: Icon) -> None:
    """Two-wheeled dray facing left, loaded with crates, a cask and a sack; shafts on the cobbles."""
    x0, x1, bt, bb = 62, 262, 742, 800
    wx, wy, wr = 170, 842, 86
    wheel(ic, wx - 20, wy - 18, wr * 0.96, tone=0.5)
    timber(ic, (x0 + 30, bb - 24), (20, GROUND - 22), 16, "#5e4430", "#3a2818")
    # load (behind the side boards): crates stacked on the left, a cask standing clear on the right
    crate(ic, 78, 664, 178, 752, top=26)
    crate(ic, 92, 604, 164, 644, top=20, c=("#9a7650", "#5a3c22"))
    tint(ic, ic.mask("rectangle", (78, 646, 178, 686)), None, (0, 0, 0), 0.3, 8)
    tint(ic, ic.mask("rectangle", (170, 640, 196, 752)), None, (0, 0, 0), 0.35, 8)  # gap shadow
    cask(ic, 190, 624, 250, 752, wood=("#ae8254", "#4a3020"))
    ic.rect((x0 + 30, bb - 4, x1 - 20, bb + 22), "#4a3424", "#2a1c12", edge=4)
    side = [(x0, bt), (x1, bt), (x1 - 6, bb), (x0 + 8, bb)]
    sm = hboards(ic, side, "#9a724a", "#553a24", board=20)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, bt, x1, bb)), sm, (0, 0, 0), 0.22, 30)
    for x in (x0 + 16, 162, x1 - 16):
        timber(ic, (x, bt - 16), (x - 2, bb + 2), 14, "#7a5638", "#4a3220")
    ic.outline(side, 5)
    wheel(ic, wx, wy, wr)
    timber(ic, (x0 + 16, bb - 6), (14, GROUND - 4), 18, "#8a6444", "#4e3522")


def handcart(ic: Icon) -> None:
    """Porter's two-wheeled handcart with a crate and hessian sacks, short handles to the right,
    resting on its leg."""
    x0, x1, bt, bb = 648, 812, 800, 840
    wx, wy, wr = 728, 872, 58
    wheel(ic, wx - 14, wy - 14, wr * 0.96, spokes=8, tone=0.5)
    timber(ic, (x1 - 20, bt + 6), (852, 786), 14, "#5e4430", "#3a2818")
    crate(ic, 660, 726, 748, 804, top=22, c=("#94704a", "#56391f"))
    sack(ic, 782, bt + 4, 70, 70, c=("#b4926a", "#56422a"), lean=0.3)
    sack(ic, 704, 708, 78, 56, c=("#a8865c", "#503c26"), lean=-0.2)
    side = [(x0, bt), (x1, bt), (x1 - 4, bb), (x0 + 6, bb)]
    sm = hboards(ic, side, "#9a724a", "#553a24", board=20)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, bt, x1, bb)), sm, (0, 0, 0), 0.22, 20)
    ic.outline(side, 4)
    timber(ic, (x0 + 30, bb - 4), (x0 + 30, GROUND), 14, "#7a5638", "#4a3220")  # leg
    timber(ic, (x1 - 30, bt + 14), (866, 798), 16, "#8a6444", "#4e3522")  # handle
    wheel(ic, wx, wy, wr, spokes=8)


def street(ic: Icon) -> None:
    top, bot = BASE - 8, 966
    pts = [(24, top), (956, top), (964, bot - 18), (940, bot), (40, bot), (16, bot - 18)]
    m = ic.poly_mask(pts)
    stones(ic, (16, top, 964, bot), "#a09684", "#6c6456", course=20, lit=60, shadow=120, moss=0.03, clip=m)
    ic.line([(30, 936), (952, 936)], 8, (60, 54, 46, 120))  # gutter
    tint(ic, ic.mask("rectangle", (0, top, ic.size, top + 24)), m, (0, 0, 0), 0.35, 10)
    ic.outline(pts, 5)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 1.0
    office(ic)
    street(ic)
    tint(ic, ic.mask("ellipse", (20, GROUND - 26, 290, GROUND + 22)), None, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("ellipse", (630, GROUND - 22, 880, GROUND + 18)), None, (0, 0, 0), 0.45, 12)
    sign(ic)
    dray(ic)
    handcart(ic)
