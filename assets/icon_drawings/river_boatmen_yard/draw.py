"""River Boatmen's Yard (river_boatmen_yard): barges towed along a river bank by a horse on the tow path.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/river_boatmen_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/river_boatmen_yard

Identity: two long, low, flat-bottomed barges roped in a train on calm green river water, the lead
barge's short towing mast with its line running to a tow horse on the tow path, and the boatmen's
tall-gabled timber boathouse with rope coils, oars and poles on the piled bank behind. No sail, no stone quay
(that is the Coastal Shipping Office), no white surf.
Transport-family helpers copied from carrier_inn; local: ``horse`` (the carrier inn's packhorse,
here in a padded towing collar), ``river``, ``bank``, ``shed``, ``barge``, ``coil``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 9
REFS = ("fishing_village", "pound_lock_canal_infrastructure", "bridge_infrastructure", "wharf")

WTOP, WBOT = 636, 812  # river band
PATH0, PATH1 = 548, 596  # tow path on the bank top
BANKFOOT = 668  # where the piles meet the water
WATERLINE = 748
RIVER_LIGHT, RIVER_DEEP = "#7aa6a0", "#2c5048"
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
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.28, cx + w, base + 10)), body, (24, 14, 6), 0.4, 10)  # underside
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


def coil(ic: Icon, cx, cy, r, peg: bool = True) -> None:
    """Coil of tarred hemp rope hung on a peg: a thick loop of twisted turns, the loose end hanging."""
    if peg:
        timber(ic, (cx - 4, cy - r * 0.95 - 14), (cx + 10, cy - r * 0.95 + 6), 10, "#8a6444", "#4a3220")
    outer = (cx - r, cy - r * 0.95, cx + r, cy + r * 1.05)
    inner = (cx - r * 0.42, cy - r * 0.3, cx + r * 0.42, cy + r * 0.5)
    ring = ImageChops.subtract(ic.mask("ellipse", outer), ic.mask("ellipse", inner))
    ic.fill(ring, "#a88452", "#4e3820", radial=(cx - r * 0.5, cy - r * 0.7, r * 2.1), noise=0.18)
    # twist: short slanted strokes following the turns
    lay_pts = []
    for f in (0.55, 0.72, 0.9):
        for a in np.linspace(0, 2 * math.pi, int(10 + 10 * f), endpoint=False):
            px = cx + math.cos(a) * r * f
            py = cy + 0.05 * r + math.sin(a) * r * f
            lay_pts.append((px, py, a))
    ic.overlay(lambda d: [d.line([(px - 4, py - 5), (px + 4, py + 5)], fill=(52, 34, 18, 150), width=3)
                          for px, py, _ in lay_pts], ring)
    ic.overlay(lambda d: [d.line([(px - 5, py - 2), (px, py - 7)], fill=(236, 206, 150, 90), width=2)
                          for px, py, a in lay_pts if math.cos(a + 2.4) > 0.2], ring)
    tint(ic, ic.mask("ellipse", (cx - r * 0.1, cy, cx + r * 1.3, cy + r * 1.4)), ring, (10, 6, 2), 0.3, r * 0.2)
    rim(ic, ring, 3, (40, 26, 12), 0.7)
    # loose end hanging below
    rope(ic, [(cx + r * 0.3, cy + r * 0.9), (cx + r * 0.36, cy + r * 1.3), (cx + r * 0.26, cy + r * 1.6)], 5)


# ---------------------------------------------------------------- tow horse
def horse(ic: Icon, X: float, G: float, s: float = 1.0, bend: float = 0.12) -> tuple[float, float]:
    """Bay draught horse in profile facing left, leaning into a padded towing collar; lit from the upper
    left (warm back, rump and neck crest, dark belly and far legs, hoof contact shadows). Returns the
    point on the traces behind the shoulder that the tow line is made fast to."""

    def sm(t: float) -> float:
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def turn(x: float, y: float) -> tuple[float, float]:
        w = sm((130 - x) / 90) * sm((y - 230) / 60)
        a = bend * w
        dx, dy = x - 130, y - 290
        return 130 + dx * math.cos(a) - dy * math.sin(a), 290 + dx * math.sin(a) + dy * math.cos(a)

    def P(pts):
        out = []
        for x, y in pts:
            u, v = turn(x, y)
            out.append((X + u * s, G - v * s))
        return out

    for hx, hw in ((40, 42), (122, 38), (268, 40), (320, 40)):
        cx = X + (hx + hw / 2) * s
        tint(ic, ic.mask("ellipse", (cx - 34 * s, G - 8 * s, cx + 34 * s, G + 12 * s)), None, (10, 6, 2), 0.6, 5)
    # legs staggered in the pull: near fore reaching, near hind driving back
    far_fore = P([(100, 200), (112, 120), (122, 64), (124, 26), (122, 0), (160, 0), (154, 24), (150, 64), (146, 120),
                  (156, 200)])
    far_hind = P([(262, 200), (270, 140), (284, 92), (282, 40), (276, 22), (268, 0), (308, 0), (306, 22), (310, 40),
                  (316, 96), (330, 124), (338, 170), (330, 215)])
    for leg in (far_fore, far_hind):
        m = ic.poly_mask(leg)
        ic.fill(m, "#4a2e1c", "#160c06", (G - 200 * s, G), noise=0.14)
        rim(ic, m, 3, (14, 8, 4), 0.6)
    tail = P([(372, 262), (394, 250), (408, 190), (404, 120), (396, 92), (380, 110), (376, 176), (364, 232)])
    ic.fill(ic.poly_mask(tail), "#3a2418", "#120a06", (G - 262 * s, G - 92 * s), noise=0.2)
    ic.overlay(lambda d: [d.line([P([(380 + i * 6, 240)])[0], P([(384 + i * 6, 110 + i * 8)])[0]],
                                 fill=(110, 76, 48, 120), width=3) for i in range(4)])
    body = P([(44, 215), (52, 185), (90, 168), (180, 158), (260, 166), (300, 184), (330, 190), (370, 215), (384, 248),
              (372, 272), (330, 286), (250, 272), (170, 274), (126, 290), (96, 322), (64, 362), (40, 390), (26, 398),
              (8, 394), (-10, 370), (-30, 330), (-46, 298), (-54, 282), (-46, 268), (-24, 268), (-4, 282), (14, 300),
              (34, 298), (50, 270)])
    near_fore = P([(56, 206), (58, 120), (54, 64), (46, 26), (36, 0), (78, 0), (82, 24), (86, 64), (100, 120),
                   (122, 200)])
    near_hind = P([(290, 200), (300, 140), (322, 94), (328, 40), (326, 22), (322, 0), (362, 0), (358, 22), (356, 40),
                   (356, 96), (364, 124), (374, 170), (366, 220)])
    bm = union(ic.poly_mask(body), ic.poly_mask(near_fore), ic.poly_mask(near_hind))
    xs = [p[0] for p in body]
    ic.fill(bm, "#a8683a", "#3a1c0a", radial=(min(xs) + 60 * s, G - 420 * s, 480 * s), noise=0.14)
    lit = ImageChops.subtract(bm, ImageChops.offset(bm, int(12 * s), int(26 * s)))
    tint(ic, lit, bm, (255, 208, 150), 0.42, 7 * s)
    under = ImageChops.subtract(bm, ImageChops.offset(bm, int(-6 * s), int(-30 * s)))
    tint(ic, under, bm, (12, 6, 2), 0.5, 10 * s)
    tint(ic, ic.mask("rectangle", (X, G - 196 * s, X + 400 * s, G)), bm, (10, 4, 0), 0.3, 16 * s)
    tint(ic, ic.mask("ellipse", tuple(P([(276, 282)])[0]) + tuple(P([(356, 206)])[0])), bm, (255, 214, 170), 0.26, 12)
    tint(ic, ic.mask("ellipse", (X + 150 * s, G - 250 * s, X + 300 * s, G - 150 * s)), bm, (10, 4, 0), 0.25, 16)
    tint(ic, ic.mask("rectangle", (X, G - 70 * s, X + 400 * s, G)), bm, (20, 12, 8), 0.7, 6)
    for hx in (36, 322):
        ic.fill(ic.intersect(bm, ic.mask("rectangle", (X + hx * s - 8, G - 16 * s, X + (hx + 44) * s, G + 2))),
                "#4a3e34", "#1a140e", noise=0.1)
    rim(ic, bm, 3, (30, 14, 6), 0.7)
    mane = P([(128, 292), (98, 328), (66, 368), (40, 396), (30, 384), (54, 354), (84, 316), (114, 286)])
    ic.fill(ic.poly_mask(mane), "#2e1c12", "#0e0806", noise=0.2)
    ic.poly(P([(30, 398), (38, 428), (50, 400)]), "#9a643a", "#3a2214", edge=3)
    ex, ey = P([(4, 366)])[0]
    ic.draw.ellipse((ex - 5, ey - 4, ex + 5, ey + 4), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 4, ey - 3, ex - 1, ey - 1), fill=(190, 180, 170, 255))
    ic.line(P([(-34, 312), (-8, 330), (14, 356), (22, 388)]), 5, (60, 36, 22))  # bridle
    # back pad and belly band
    pad = P([(170, 284), (200, 290), (230, 284), (236, 250), (200, 244), (168, 250)])
    ic.fill(ic.poly_mask(pad), "#7a5434", "#34200f", (G - 290 * s, G - 244 * s), noise=0.12)
    ic.outline(pad, 3, (30, 18, 10, 200))
    ic.line(P([(202, 246), (200, 164)]), 8, (54, 34, 20))
    # padded collar: a thick leather ring round the neck base, lit along its upper-left edge
    cl = [(128, 322), (112, 300), (96, 270), (82, 240), (72, 214), (70, 194), (78, 182)]
    ctr = P(cl)
    half = 24 * s
    left, right = [], []
    for i, (px, py) in enumerate(ctr):
        qx, qy = ctr[min(i + 1, len(ctr) - 1)]
        rx, ry = ctr[max(i - 1, 0)]
        dx, dy = qx - rx, qy - ry
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = half * (0.55 + 0.45 * math.sin(math.pi * i / (len(ctr) - 1)))
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    collar = left + right[::-1]
    km = ic.poly_mask(collar)
    ic.fill(km, "#6e4a2c", "#24160a", radial=(ctr[1][0] - 20 * s, ctr[1][1] - 30 * s, 150 * s), noise=0.12)
    edge = ImageChops.subtract(km, ImageChops.offset(km, int(8 * s), int(10 * s)))
    tint(ic, edge, km, (240, 196, 140), 0.55, 3)
    ic.outline(collar, 3, (26, 16, 8, 210))
    tint(ic, ImageChops.subtract(km, ImageChops.offset(km, int(-8 * s), int(-8 * s))), km, (10, 6, 2), 0.45, 3)
    ic.line([(p[0] + 8 * s, p[1] - 3 * s) for p in ctr[1:5]], max(3, int(6 * s)), (196, 168, 110))  # hames
    ic.line([(p[0] + 6 * s, p[1] - 6 * s) for p in ctr[1:5]], 2, (250, 232, 180, 170))
    # traces from the hames back along the flank; the tow line is made fast behind the shoulder
    ic.line(P([(92, 246), (150, 236), (196, 232)]), max(4, int(7 * s)), (58, 38, 22))
    ic.line(P([(92, 250), (150, 240), (196, 236)]), max(2, int(3 * s)), (150, 112, 70, 160))
    hook = P([(196, 234)])[0]
    ic.overlay(lambda d: d.ellipse((hook[0] - 7, hook[1] - 7, hook[0] + 7, hook[1] + 7), outline=(60, 56, 52, 255),
                                   width=4))
    return hook


# ---------------------------------------------------------------- river, bank, shed
def river(ic: Icon) -> Image.Image:
    band = ic.water_band(top=WTOP, bottom=WBOT, x0=16, x1=1008, inset=34, sag=34, light=RIVER_LIGHT,
                         deep=RIVER_DEEP, surf=False)
    rnd = ic.random.uniform

    def ripples(d: ImageDraw.ImageDraw) -> None:
        for y in range(WTOP + 30, WBOT + 30, 26):
            x = rnd(-60, 0)
            while x < ic.size:
                ln = rnd(30, 110)
                d.line([(x, y), (x + ln, y + rnd(-2, 2))], fill=(214, 234, 226, int(rnd(60, 140))), width=4)
                d.line([(x + 12, y + 8), (x + ln - 6, y + 8)], fill=(18, 44, 40, 90), width=4)
                x += ln + rnd(40, 140)

    ic.overlay(ripples, band)
    tint(ic, ic.mask("rectangle", (0, WTOP, ic.size, WTOP + 40)), band, (230, 240, 225), 0.18, 14)  # far water lit
    return band


def bank(ic: Icon) -> None:
    """Bank strip behind the river: the lit tow path on top, a grassy slope, a piled timber revetment."""
    x0, x1 = 40, 984
    slope = [(x0, PATH1), (x1, PATH1), (x1 + 4, BANKFOOT), (x0 - 4, BANKFOOT)]
    sm = ic.poly_mask(slope)
    ic.fill(sm, "#7a7a44", "#4a4a28", (PATH1, BANKFOOT), noise=0.3)
    rnd = ic.random.uniform

    def grass(d: ImageDraw.ImageDraw) -> None:
        for _ in range(420):
            x, y = rnd(x0, x1), rnd(PATH1, BANKFOOT)
            ln = rnd(8, 20)
            t = rnd(-1, 1)
            col = (214, 206, 130, int(t * 140)) if t > 0 else (30, 36, 12, int(-t * 140))
            d.line([(x, y), (x + rnd(-5, 5), y - ln)], fill=col, width=3)

    ic.overlay(grass, sm)
    rev = [(x0 - 4, BANKFOOT - 40), (x1 + 4, BANKFOOT - 40), (x1 + 4, BANKFOOT + 16), (x0 - 4, BANKFOOT + 16)]
    hboards(ic, rev, "#7a5a3c", "#3e2c1c", board=18)
    tint(ic, ic.poly_mask(rev), None, (20, 30, 20), 0.22)
    for x in np.arange(x0 + 6, x1, 46):
        x += rnd(-4, 4)
        top = BANKFOOT - 58 + rnd(-6, 6)
        timber(ic, (x, top), (x, BANKFOOT + 24), 18, "#8a6444", "#3e2c1c")
        ic.ellipse((x - 10, top - 6, x + 10, top + 6), "#b08a60", "#6a4e30", edge=3)
    ic.outline(rev, 4)
    path = [(x0 + 10, PATH0), (x1 - 10, PATH0), (x1, PATH1), (x0, PATH1)]
    pm = ic.poly_mask(path)
    ic.fill(pm, "#c4aa7c", "#94784e", (PATH0, PATH1), noise=0.3)

    def marks(d: ImageDraw.ImageDraw) -> None:
        for _ in range(70):
            x, y = rnd(x0, x1), rnd(PATH0 + 6, PATH1 - 6)
            d.ellipse((x - 6, y - 3, x + 6, y + 3), fill=(70, 52, 30, int(rnd(60, 130))))
        x = x0
        while x < x1:
            ln = rnd(60, 180)
            d.line([(x, 574 + rnd(-3, 3)), (x + ln, 574 + rnd(-3, 3))], fill=(236, 220, 180, 70), width=6)
            x += ln + rnd(20, 60)

    ic.overlay(marks, pm)
    ic.line([(x0, PATH1), (x1, PATH1)], 6, (50, 40, 24, 150))
    ic.outline(path, 4)


SX0, SX1, EAVE, APEX = 588, 976, 306, 34  # boathouse


def shed(ic: Icon) -> None:
    """Boatmen's boathouse on the bank: tall steep boarded gable with a loft door, wide open front hung
    with rope coils, oars and poles, casks in the dark; weathered wooden-shingle roof."""
    x0, x1, base, eave, apex = SX0, SX1, PATH0 + 6, EAVE, APEX
    cx = (x0 + x1) / 2
    rr = [(cx + 4, apex - 10), (x1 + 44, eave - 8), (x1 + 56, eave + 22), (cx + 4, apex + 40)]
    m = shingles(ic, rr, "#86725a", "#463a30", course=22, stagger=30, edge=6)
    tint(ic, m, m, (0, 0, 0), 0.2)
    gable = [(x0, base), (x0, eave), (cx, apex + 24), (x1, eave), (x1, base)]
    gm = planks(ic, gable, "#9a7c5c", "#54402c", board=30)
    tint(ic, ic.mask("rectangle", (x0, apex, x1, apex + 220)), gm, (0, 0, 0), 0.3, 24)
    tint(ic, ic.mask("rectangle", (cx + 60, apex, x1, base)), gm, (0, 0, 0), 0.22, 30)
    tint(ic, ic.mask("rectangle", (x0, base - 60, x1, base)), gm, (40, 46, 20), 0.25, 18)
    # loft door with a hoist beam and a coil on a peg
    ic.rect((cx - 46, 196, cx + 46, 300), "#2a1f16", "#120c08", noise=0.1, edge=4)
    ic.rect((cx - 56, 184, cx + 56, 198), "#7a5638", "#4a3220", edge=3)
    timber(ic, (cx, 150), (cx, 184), 22, "#8e6646", "#4e3522")
    coil(ic, cx - 4, 250, 30, peg=False)
    # wide open front
    ox0, ox1, oy0 = x0 + 34, x1 - 34, 356
    op = ic.mask("rectangle", (ox0, oy0, ox1, base))
    ic.fill(op, "#3a2c20", "#140e0a", (oy0, base), noise=0.1)
    with ic.clipped(op):
        planks(ic, [(ox0, oy0), (ox1, oy0), (ox1, base), (ox0, base)], "#4e3a28", "#2a1e14", 34)  # back wall
        for x, lean in ((826, -18), (850, 8), (872, -6)):
            timber(ic, (x + lean, oy0 + 4), (x, base - 2), 12, "#8a6848", "#4a3420")
        for x in (896, 918):  # oars, blades down
            timber(ic, (x, oy0 + 10), (x + 4, base - 50), 10, "#9a7650", "#56402a")
            ic.poly([(x - 10, base - 60), (x + 16, base - 60), (x + 14, base - 4), (x - 8, base - 4)], "#9a7650",
                    "#56402a", edge=3)
        cask(ic, 650, 470, 704, base - 2, wood=("#7e5c3c", "#34241a"))
        cask(ic, 700, 482, 748, base, wood=("#72543a", "#2e2014"))
        tint(ic, op, None, (0, 0, 0), 0.25)
        tint(ic, ic.mask("rectangle", (ox0, oy0, ox1, oy0 + 50)), None, (0, 0, 0), 0.5, 14)
        for ccx, ccy, r in ((676, 414, 30), (752, 404, 26)):
            coil(ic, ccx, ccy, r)
    timber(ic, (ox0 - 6, oy0 - 8), (ox1 + 6, oy0 - 8), 22, "#8e6646", "#4e3522")
    for x in (ox0 - 4, ox1 + 4):
        timber(ic, (x, oy0 - 4), (x, base + 4), 20, "#8e6646", "#4e3522")
    ic.outline(gable, 5)
    lv = [(cx - 4, apex - 10), (x0 - 44, eave - 8), (x0 - 24, eave + 22), (cx - 4, apex + 40)]
    shingles(ic, lv, "#a48e70", "#5e4e3e", course=22, stagger=30, edge=6)
    rv = [(cx - 4, apex - 10), (x1 + 44, eave - 8), (x1 + 24, eave + 22), (cx - 4, apex + 40)]
    vm = shingles(ic, rv, "#8a765e", "#4a3e32", course=22, stagger=30, edge=6)
    tint(ic, vm, vm, (0, 0, 0), 0.12)
    for poly in (lv, rv):
        for _ in range(3):
            xx = ic.random.uniform(min(p[0] for p in poly), max(p[0] for p in poly))
            yy = ic.random.uniform(apex, eave)
            tint(ic, ic.mask("ellipse", (xx - 40, yy - 14, xx + 40, yy + 14)), ic.poly_mask(poly), (90, 104, 50), 0.3, 10)
    tint(ic, ic.poly_mask([(cx, apex + 30), (x0 - 10, eave + 20), (x0 + 40, eave + 44), (cx, apex + 80)]), gm,
         (0, 0, 0), 0.35, 12)
    tint(ic, ic.poly_mask([(cx, apex + 30), (x1 + 10, eave + 20), (x1 - 40, eave + 44), (cx, apex + 80)]), gm,
         (0, 0, 0), 0.35, 12)
    timber(ic, (cx, apex - 30), (cx, apex + 6), 12, "#8e6646", "#4e3522")  # finial


# ---------------------------------------------------------------- barges
def barge(ic: Icon, band: Image.Image, x0: float, x1: float, top: float, cargo) -> Image.Image:
    """Long flat-bottomed river barge in profile, bow raked up at the left; returns the hull mask."""
    bot = WATERLINE + 34
    far = [(x0 + 20, top - 50), (x0 + 90, top - 30), (x1 - 20, top - 32), (x1 + 2, top - 40)]
    gun = [(x0, top - 30), (x0 + 30, top - 10), (x0 + 90, top), (x1 - 30, top), (x1, top - 10)]
    ic.poly(far + gun[::-1], "#4e3624", "#2a1c10", edge=0)
    cargo()
    ic.line(far, 10, (120, 86, 56))
    ic.line(far, 3, (40, 28, 20, 200))
    hull = gun + [(x1 - 4, bot - 20), (x1 - 20, bot), (x0 + 110, bot), (x0 + 10, top - 14)]
    hm = hboards(ic, hull, "#86603c", "#34241a", board=22)
    tint(ic, ic.mask("rectangle", (x0, top + 34, x1, bot)), hm, (10, 6, 2), 0.4, 12)
    tint(ic, ic.mask("rectangle", (x0, WATERLINE - 24, x1, bot)), hm, (6, 4, 2), 0.5, 6)  # wet, shadowed waterline
    tint(ic, ic.mask("rectangle", (x0, top - 40, x0 + 140, bot)), hm, (255, 230, 190), 0.14, 24)
    ic.line(gun, 18, (40, 28, 20, 220))
    ic.line(gun, 11, (196, 156, 102))  # sunlit rubbing strake
    ic.line([(x, y - 3) for x, y in gun], 3, (244, 220, 170, 200))
    for x in np.linspace(x0 + 120, x1 - 30, 5):  # knees / tholes
        ic.line([(x, top - 4), (x, top - 20)], 8, (122, 88, 56))
    ic.outline(hull, 5)
    whole = hm.filter(ImageFilter.MaxFilter(9))
    ic.waterline(whole, WATERLINE)
    tint(ic, ic.intersect(ic.mask("rectangle", (x0 - 10, WATERLINE, x1 + 10, WATERLINE + 34)), band), band,
         (6, 20, 18), 0.55, 10)

    def foam(d: ImageDraw.ImageDraw) -> None:
        for x in np.arange(x0 + 10, x1 - 10, 44):
            ln = ic.random.uniform(16, 34)
            yy = WATERLINE + ic.random.uniform(-3, 5)
            d.line([(x, yy), (x + ln, yy)], fill=(214, 234, 226, int(ic.random.uniform(60, 170))), width=5)

    ic.overlay(foam, band)
    return hm


def lead_cargo(ic: Icon) -> None:
    """Hessian sacks and a crate forward, bales under a roped ochre canvas aft."""
    sack(ic, 150, 666, 78, 64, c=("#b4926a", "#56422a"), lean=0.2)
    sack(ic, 214, 668, 80, 72, c=("#a88458", "#503c26"))
    sack(ic, 282, 666, 86, 76, c=("#bc9e72", "#5e4a32"))
    crate(ic, 320, 616, 420, 664, top=22)
    tarp = [(430, 664), (436, 588), (470, 548), (540, 532), (610, 540), (648, 584), (656, 664)]
    tm = ic.poly_mask(tarp)
    ic.fill(tm, "#b08e50", "#584020", radial=(460, 520, 260), noise=0.18, chroma=0.04)
    for x in (478, 540, 604):  # folds between the lashings
        tint(ic, ic.poly_mask([(x + 8, 540), (x + 30, 540), (x + 36, 664), (x + 12, 664)]), tm, (30, 20, 8), 0.3, 8)
        tint(ic, ic.poly_mask([(x - 16, 540), (x - 4, 540), (x, 664), (x - 12, 664)]), tm, (255, 236, 196), 0.18, 6)
    tint(ic, ic.mask("rectangle", (430, 628, 660, 670)), tm, (20, 12, 4), 0.35, 10)
    for x in (470, 532, 596, 640):  # ropes over the canvas
        rope(ic, [(x - 10, 560 if x < 630 else 590), (x - 4, 610), (x, 664)], 4)
    rope(ic, [(436, 612), (540, 600), (650, 614)], 4)
    ic.outline(tarp, 4, (40, 30, 14, 200))


def tail_cargo(ic: Icon) -> None:
    """Casks and a stack of sawn timber."""
    for i, x in enumerate((704, 758)):
        cask(ic, x, 612 + i * 8, x + 52, 690, wood=("#a47a50", "#4a3020"))
    for k, y in enumerate((664, 642, 620, 598)):
        ic.rect((826 + k * 8, y, 980 - k * 10, y + 22), "#c49a66", "#7a5a38", edge=3)
    tint(ic, ic.mask("rectangle", (820, 598, 990, 690)), None, (0, 0, 0), 0.12, 10)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    shed(ic)
    bank(ic)
    band = river(ic)
    ic.rect((720, BANKFOOT - 12, 986, BANKFOOT + 8), "#a88058", "#6a4a2e", edge=4)  # landing stage
    hook = horse(ic, 70, PATH1 - 4, 0.86)
    # tail barge first (it lies a touch further out), then the lead barge with its towing mast
    barge(ic, band, 684, 1004, 690, lambda: tail_cargo(ic))
    rope(ic, [(688, 668), (676, 680), (664, 672)], 4)
    mx, mtop = 520, 250
    barge(ic, band, 44, 700, 680, lambda: lead_cargo(ic))
    timber(ic, (mx, mtop), (mx, 670), 20, "#96704a", "#52391f")
    ic.ellipse((mx - 13, mtop - 12, mx + 13, mtop + 10), "#a07650", "#6a4a30", edge=4)
    # tow line: from the traces behind the shoulder, one clean sagging curve up to the mast head
    p0, p2 = hook, (mx - 4, mtop + 6)
    c = ((p0[0] + p2[0]) / 2 + 40, max(p0[1], p2[1]) + 30)
    curve = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p2[0],
              (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p2[1]) for t in np.linspace(0, 1, 40)]
    rope(ic, curve, 7)
