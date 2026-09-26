"""Coastal Shipping Office (coastal_shipping_office): a quay office with a coasting ship moored alongside.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/coastal_shipping_office/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/coastal_shipping_office

Identity: a single-masted coaster with a big pale square sail, a red strake and a raised stern
deck, moored at a stone quay; on the quay a gable-fronted stone shipping office with a hoist beam
lifting a bale into its loft, tar barrels and a bollard. Stands on the vanilla sea band (fishing
village, dock, wharf). The Coastal Fishery has a small boat with a brown sail and nets instead.
Transport-family helpers copied from carrier_inn; local: ``quay``, ``office``, ``ship``, ``bale``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE

SEED = 3
REFS = ("dock", "wharf", "cinque_port", "port_authority")

WTOP, WBOT = 704, 860  # water band
QTOP, QFACE, QWATER = 640, 690, 762  # quay: back of the paving, front edge, waterline on its face
OL, OR = 86, 404  # office walls
OCX = (OL + OR) / 2
OEAVE, OAPEX = 356, 118
BOW, STERN = 468, 1000
MAST_X = 736
WATERLINE = 772
IRON = (40, 38, 36)
WOOD = (118, 82, 52)


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
    ic.fill(ic.mask("ellipse", inner), "#c49a6c", "#8a6440", radial=(x0 + w * 0.3, y0 - lip, w * 0.9), noise=0.14)
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


def resurf(ic: Icon, band: Image.Image, mask: Image.Image, y: float) -> None:
    """Repaint water over ``mask`` below ``y`` and carry the band's wave crests across it."""
    ic.waterline(mask, y)
    area = ic.intersect(mask, ic.mask("rectangle", (0, y, ic.size, ic.size)), band)

    def strokes(d: ImageDraw.ImageDraw) -> None:
        for row, yy in enumerate(range(int(WTOP) + 40, int(WBOT + 36), 36)):
            x = -40 + (row % 2) * 60
            while x < ic.size:
                ln = ic.random.uniform(40, 90)
                yj = yy + ic.random.uniform(-8, 8)
                d.arc((x, yj - 12, x + ln, yj + 12), 200, 340, fill=(228, 242, 245, 200), width=6)
                d.line([(x + 10, yj + 10), (x + ln - 10, yj + 10)], fill=(20, 50, 66, 120), width=5)
                x += ln + ic.random.uniform(30, 80)

    ic.overlay(strokes, area)


def bale(ic: Icon, x0, y0, x1, y1, c=("#e0d6bc", "#8c8068")) -> None:
    """Rolled bolt of sailcloth lying on its side: lit cylinder, end-on spiral, cord ties."""
    h = y1 - y0
    body = [(x0 + h * 0.2, y0), (x1, y0), (x1, y1), (x0 + h * 0.2, y1)]
    bm = ic.poly_mask(body)
    ic.fill(bm, c[0], c[1], (y0, y1), noise=0.12)
    tint(ic, ic.mask("rectangle", (x0, y0 + h * 0.55, x1, y1)), bm, (30, 20, 10), 0.3, 6)
    for f in (0.35, 0.75):
        x = x0 + (x1 - x0) * f
        ic.line([(x, y0), (x + 4, y1)], 6, (110, 82, 50))
    ic.outline(body, 4, (60, 50, 34, 170))
    end = (x0, y0, x0 + h * 0.5, y1)
    ic.fill(ic.mask("ellipse", end), "#d2c6aa", "#8a7e66", radial=(x0, y0, h), noise=0.1)
    ic.overlay(lambda d: [d.ellipse((x0 + h * 0.25 * (1 - f), y0 + h * 0.5 * (1 - f), x0 + h * 0.25 * (1 + f),
                                     y0 + h * 0.5 * (1 + f)), outline=(90, 78, 58, 170), width=3) for f in (0.35, 0.7)])
    ic.overlay(lambda d: d.ellipse(end, outline=(60, 50, 34, 200), width=4))


# ---------------------------------------------------------------- quay and office
def quay(ic: Icon) -> Image.Image:
    x0, x1 = 30, 700
    top = [(x0 + 18, QTOP), (x1 - 10, QTOP), (x1, QFACE), (x0, QFACE)]
    tm = ic.poly_mask(top)
    stones(ic, (x0, QTOP, x1, QFACE), "#b8a88e", "#8e806a", course=16, lit=60, shadow=100, moss=0.02, clip=tm)
    face = [(x0, QFACE), (x1, QFACE), (x1, 820), (x0, 820)]
    fm = ic.poly_mask(face)
    stones(ic, (x0, QFACE, x1, 820), "#9a8c78", "#5a5046", course=34, moss=0.14, clip=fm)
    tint(ic, ic.mask("rectangle", (x0, QWATER - 40, x1, QWATER)), fm, (30, 50, 30), 0.35, 12)  # weed and wet stone
    ic.rect((x0 - 8, QFACE - 8, x1 + 8, QFACE + 12), "#c4b69c", "#8a7e6a", edge=4)  # coping
    tint(ic, ic.mask("rectangle", (x0, QFACE + 12, x1, QFACE + 34)), fm, (0, 0, 0), 0.35, 6)
    ic.outline(top + [(x0, QFACE)], 5)
    ic.line([(x0, QWATER), (x0, QFACE), (x1, QFACE), (x1, QWATER)], 5)
    return fm


def office(ic: Icon) -> None:
    base = QTOP + 12
    # right-hand roof slope, seen past the gable
    roof_r = [(OCX + 6, OAPEX - 6), (OR + 60, OEAVE - 14), (OR + 70, OEAVE + 20), (OR + 20, OEAVE + 24),
              (OCX + 6, OAPEX + 40)]
    rr = shingles(ic, roof_r, "#9a5a42", "#4e281c", course=22, stagger=30, edge=6)
    tint(ic, rr, rr, (0, 0, 0), 0.2)
    # side wall of the right wing under that slope
    side = ic.mask("rectangle", (OR - 6, OEAVE + 20, OR + 58, base))
    stones(ic, (OR - 6, OEAVE + 20, OR + 58, base), "#a09078", "#5e5244", course=34, clip=side)
    tint(ic, side, side, (0, 0, 0), 0.35)
    ic.outline([(OR - 6, OEAVE + 20), (OR + 58, OEAVE + 20), (OR + 58, base), (OR - 6, base)], 4)
    # gable front: limewashed stone
    front = [(OL, base), (OL, OEAVE), (OCX, OAPEX + 30), (OR, OEAVE), (OR, base)]
    fm = ic.poly_mask(front)
    stones(ic, (OL, OAPEX, OR, base), "#d6c8aa", "#9c8a6c", course=34, lit=50, shadow=80, moss=0.03, clip=fm)
    tint(ic, ic.mask("rectangle", (OL, base - 70, OR, base)), fm, (40, 46, 26), 0.22, 20)
    for _ in range(8):
        x, y = ic.random.uniform(OL, OR), ic.random.uniform(OAPEX + 60, base)
        r = ic.random.uniform(24, 50)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 1.4, x + r, y + r * 1.4)), fm, (60, 50, 30), 0.12, 14)
    # quoins
    for x0 in (OL, OR - 30):
        y = OEAVE
        k = 0
        while y < base - 30:
            w = 30 if k % 2 else 20
            h = ic.random.uniform(26, 32)
            bx = (x0, y, x0 + w, y + h) if x0 == OL else (OR - w, y, OR, y + h)
            ic.rect(bx, "#c6b69a", "#8a7c66", edge=0)
            ic.line([(bx[0], bx[3]), (bx[2], bx[3])], 3, (50, 40, 30, 150))
            y += h + 2
            k += 1
    # loft door with a hoist beam and a bale on the rope
    ic.rect((OCX - 34, 214, OCX + 34, 292), "#2a1f16", "#120c08", noise=0.1, edge=4)
    ic.rect((OCX - 44, 204, OCX + 44, 216), "#8a6444", "#4e3522", edge=3)
    ic.rect((OCX - 18, 150, OCX + 18, 180), "#9a7050", "#523823", edge=4)  # hoist beam end
    ic.ellipse((OCX - 14, 176, OCX + 14, 204), "#6a625c", "#2e2a28", edge=3)
    rope(ic, [(OCX + 10, 196), (OCX + 10, 300)], 4)
    ic.draw.ellipse((OCX + 1, 296, OCX + 19, 314), outline=IRON + (255,), width=5)
    bale(ic, OCX - 52, 314, OCX + 70, 366)
    # windows and door
    for x0, x1 in ((OL + 40, OL + 96), (OR - 96, OR - 40)):
        ic.window(x0, 392, x1, 470)
        tint(ic, ic.mask("rectangle", (x0 - 10, 480, x1 + 16, 500)), fm, (0, 0, 0), 0.25, 6)
    ic.door(OCX - 44, 526, OCX + 44, base - 4)
    ic.window(OL + 34, 548, OL + 80, 610)
    ic.window(OR - 80, 548, OR - 34, 610)
    tint(ic, ic.mask("rectangle", (OR - 70, OAPEX, OR, base)), fm, (0, 0, 0), 0.15, 30)
    ic.outline(front, 5)
    # left roof slope with a verge
    roof_l = [(OCX - 6, OAPEX - 6), (OL - 44, OEAVE - 8), (OL - 24, OEAVE + 22), (OCX - 6, OAPEX + 36)]
    shingles(ic, roof_l, "#b46a4c", "#6a3424", course=22, stagger=30, edge=6)
    roof_r2 = [(OCX - 6, OAPEX - 6), (OR + 44, OEAVE - 8), (OR + 24, OEAVE + 22), (OCX - 6, OAPEX + 36)]
    m2 = shingles(ic, roof_r2, "#9e5c42", "#56301e", course=22, stagger=30, edge=6)
    tint(ic, m2, m2, (0, 0, 0), 0.12)
    tint(ic, ic.poly_mask([(OCX, OAPEX + 30), (OL - 10, OEAVE + 20), (OL + 40, OEAVE + 44), (OCX, OAPEX + 80)]), fm,
         (0, 0, 0), 0.35, 12)
    tint(ic, ic.poly_mask([(OCX, OAPEX + 30), (OR + 10, OEAVE + 20), (OR - 40, OEAVE + 44), (OCX, OAPEX + 80)]), fm,
         (0, 0, 0), 0.35, 12)
    # chimney stack on the right slope
    cx0, cx1, ct = OR - 70, OR - 22, 150
    cm = ic.mask("rectangle", (cx0, ct, cx1, 270))
    stones(ic, (cx0, ct, cx1, 270), "#b0a492", "#6e6456", course=22, clip=cm)
    tint(ic, ic.mask("rectangle", (cx0 + 26, ct, cx1, 270)), cm, (0, 0, 0), 0.3, 8)
    ic.outline([(cx0, ct), (cx1, ct), (cx1, 270), (cx0, 270)], 4)
    ic.poly([(cx0 - 8, ct - 10), (cx1 + 8, ct - 10), (cx1 + 8, ct + 6), (cx0 - 8, ct + 6)], "#bcb09c", "#7c7264", edge=4)


def quay_props(ic: Icon) -> None:
    tint(ic, ic.mask("ellipse", (290, QFACE - 26, 430, QFACE + 14)), None, (0, 0, 0), 0.4, 10)
    cask(ic, 300, 596, 364, QFACE - 4, wood=("#5a4636", "#1e1610"))
    cask(ic, 356, 614, 410, QFACE, wood=("#4e3c2e", "#1a120c"))
    bale(ic, 20, 632, 150, 690)
    tint(ic, ic.mask("ellipse", (10, QFACE - 16, 170, QFACE + 12)), None, (0, 0, 0), 0.4, 8)
    # bollard at the quay edge
    ic.rect((430, 640, 458, 688), "#5a5450", "#2a2624", edge=4)
    ic.ellipse((424, 630, 464, 650), "#7a7470", "#3a3634", edge=4)


# ---------------------------------------------------------------- the coaster
def castle(t):
    """Rise of the gunwale into the raised stern deck."""
    u = np.clip((t - 0.72) / 0.08, 0, 1)
    return 74 * u * u * (3 - 2 * u)


def sheer(t):
    return 572 * (1 - t) + 556 * t + 56 * np.sin(np.pi * t) ** 0.9 - castle(t)


def depth(t):
    return 26 + 200 * np.sin(np.pi * t) ** 0.45


def ship(ic: Icon, band: Image.Image) -> None:
    ts = np.linspace(0, 1, 48)
    xs = BOW + (STERN - BOW) * ts
    g = [(x, sheer(t)) for x, t in zip(xs, ts)]
    far = [(x, sheer(t) - 44 * np.sin(np.pi * t) ** 0.7) for x, t in zip(xs, ts)]
    bottom = [(x, sheer(t) + depth(t)) for x, t in zip(xs, ts)]
    mt = (MAST_X - BOW) / (STERN - BOW)

    # rigging behind the sail
    top = 58
    ic.line([(MAST_X, top + 20), (BOW - 10, 520)], 5, (58, 40, 26))
    ic.line([(MAST_X, top + 20), (STERN - 30, 470)], 5, (58, 40, 26))
    for dx in (-14, 14):
        ic.line([(MAST_X, top + 40), (MAST_X + dx * 7, sheer(mt) - 20)], 3, (70, 52, 34, 200))
    ic.beam((MAST_X, top), (MAST_X, 620), 26, WOOD)
    # square sail set on its yard, bellied, pale canvas
    yl, yr = (MAST_X - 170, 132), (MAST_X + 170, 118)
    fl, fr = (MAST_X - 156, 452), (MAST_X + 184, 440)
    s16 = np.linspace(0, 1, 18)
    top_e = [(yl[0] + (yr[0] - yl[0]) * t, yl[1] + (yr[1] - yl[1]) * t) for t in s16]
    right_e = [(yr[0] + (fr[0] - yr[0]) * t + 30 * np.sin(np.pi * t), yr[1] + (fr[1] - yr[1]) * t) for t in s16]
    foot = [(fr[0] + (fl[0] - fr[0]) * t, fr[1] + (fl[1] - fr[1]) * t - 28 * np.sin(np.pi * t)) for t in s16]
    left_e = [(fl[0] + (yl[0] - fl[0]) * t + 16 * np.sin(np.pi * t), fl[1] + (yl[1] - fl[1]) * t) for t in s16]
    sail = top_e + right_e + foot + left_e
    sm = ic.poly_mask(sail)
    ic.fill(sm, "#ece2c8", "#a89a7c", (yl[0], fr[0] + 30), vertical=False, noise=0.12, chroma=0.04)
    for f in np.linspace(0.14, 0.86, 6):  # cloth panels: seam plus a soft fold beside it
        a = (yl[0] + (yr[0] - yl[0]) * f, yl[1] + (yr[1] - yl[1]) * f)
        b = (fl[0] + (fr[0] - fl[0]) * f + 20 * np.sin(np.pi * f), fl[1] + (fr[1] - fl[1]) * f - 28 * np.sin(np.pi * f))
        mid = ((a[0] + b[0]) / 2 + 12, (a[1] + b[1]) / 2)
        ic.line([a, mid, b], 3, (110, 96, 70, 170))
        fold = ic.poly_mask([(a[0] + 4, a[1]), (a[0] + 26, a[1]), (mid[0] + 30, mid[1]), (b[0] + 26, b[1]), (b[0] + 4, b[1]),
                             (mid[0] + 8, mid[1])])
        tint(ic, fold, sm, (70, 58, 36), 0.18, 8)
    ic.line([(fl[0] + 10, 400), (fr[0] - 10, 388)], 3, (110, 96, 70, 150))  # reef band
    tint(ic, ic.mask("rectangle", (MAST_X + 40, 0, ic.size, ic.size)), sm, (20, 14, 6), 0.22, 40)
    tint(ic, ic.mask("rectangle", (0, 400, ic.size, 480)), sm, (40, 30, 16), 0.2, 20)
    ic.outline(sail, 6)
    ic.beam((yl[0] - 18, yl[1] + 2), (yr[0] + 18, yr[1] - 2), 16, WOOD)
    ic.line([fr, (STERN - 60, 520)], 5, (58, 40, 26))
    ic.line([fl, (BOW + 40, 540)], 5, (58, 40, 26))
    # masthead pennant
    ts2 = np.linspace(0, 1, 20)
    pt = [(MAST_X + 6 + 150 * t, top - 4 + 12 * t + 8 * math.sin(math.pi * 2 * t)) for t in ts2]
    pb = [(MAST_X + 6 + 150 * t, top + 26 - 12 * t + 8 * math.sin(math.pi * 2 * t + 0.4)) for t in ts2]
    pen = pt + [(MAST_X + 170, top + 6)] + pb[::-1]
    ic.fill(ic.poly_mask(pen), "#b24a36", "#5e2418", (MAST_X, MAST_X + 170), vertical=False, noise=0.12)
    ic.outline(pen, 4, (50, 22, 14, 170))
    ic.ellipse((MAST_X - 12, top - 20, MAST_X + 12, top + 2), "#8a6444", "#4e3522", edge=4)

    # hold seen from the raised camera, with cargo
    ic.poly(far + g[::-1], "#5e4029", "#3a2616", edge=0)
    crate(ic, 560, 590, 640, 630, top=16)
    cask(ic, 640, 566, 690, 626, wood=("#a47a50", "#4a3020"))
    bale(ic, 780, 580, 870, 624)
    ic.line(far, 12, (120, 84, 54))
    ic.line(far, 4, LINE)
    ic.beam((MAST_X, 440), (MAST_X, 612), 26, WOOD)

    # hull: tarred planks under a red-painted top strake
    hull = g + bottom[::-1]
    hm = ic.poly_mask(hull)
    ic.fill(hm, "#7a5436", "#2e1e12", (520, 800))
    strake = g + [(x, sheer(t) + depth(t) * 0.22) for x, t in zip(xs[::-1], ts[::-1])]
    ic.fill(ic.poly_mask(strake), "#a4523a", "#5a2a1c", (540, 640), noise=0.14)
    for f in (0.22, 0.4, 0.56, 0.72, 0.86):
        ic.line([(x, sheer(t) + depth(t) * f) for x, t in zip(xs, ts)], 5, (38, 24, 14, 220))
    ic.shade(ic.poly_mask(g + [(x, y + 34) for x, y in g[::-1]]), alpha=0.3, blur=8)
    tint(ic, ic.poly_mask(bottom + [(x, sheer(t) + depth(t) * 0.5) for x, t in zip(xs[::-1], ts[::-1])]), hm,
         (0, 0, 0), 0.25, 14)
    tint(ic, ic.mask("rectangle", (BOW, 540, BOW + 160, 820)), hm, (255, 230, 190), 0.12, 30)
    ic.outline(hull)
    ic.line(g, 18, LINE)
    ic.line(g, 10, (150, 108, 70))
    for x in np.linspace(BOW + 70, 800, 6):  # rail stanchions
        t = (x - BOW) / (STERN - BOW)
        ic.line([(x, sheer(t) - 2), (x, sheer(t) - 30)], 8, (110, 78, 50))
    # rail on the stern deck, a cabin door in its forward bulkhead
    rail = [(x, sheer((x - BOW) / (STERN - BOW)) - 40) for x in np.linspace(832, STERN - 4, 12)]
    for x in np.linspace(840, STERN - 10, 6):
        t = (x - BOW) / (STERN - BOW)
        ic.line([(x, sheer(t) - 2), (x, sheer(t) - 40)], 8, (110, 78, 50))
    ic.line(rail, 12, LINE)
    ic.line(rail, 7, (140, 100, 64))
    # stem post and rudder
    ic.beam((BOW + 6, 590), (BOW - 22, 520), 20, WOOD)
    ic.beam((STERN - 2, 500), (STERN + 8, 700), 22, (96, 66, 42))
    # mooring line to the bollard
    ic.draw.line([(BOW - 18, 530), (446, 590), (444, 640)], fill=(70, 52, 34, 255), width=7, joint="curve")

    # stand the hull in the water
    resurf(ic, band, hm.filter(ImageFilter.MaxFilter(9)), WATERLINE)
    ic.foam(BOW + 40, STERN - 10, WATERLINE)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86
    band = ic.water_band(top=WTOP, bottom=WBOT, x0=14, x1=1010, sag=36)
    fm = quay(ic)
    resurf(ic, band, fm, QWATER)
    ic.foam(34, 470, QWATER)
    office(ic)
    quay_props(ic)
    ship(ic, band)
