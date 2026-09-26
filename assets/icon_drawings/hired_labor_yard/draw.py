"""Porters' Hall (hired_labor_yard): a town hall on an open stone arcade where porters and carters wait for hire.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/hired_labor_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/hired_labor_yard

Identity: the porters' gear standing apart on the paving below the arcade springline: a pale
carrying frame with a lashed crate, a wheelbarrow with two burlap sacks and a
dark iron-tyred wheel, a red-brown wicker back-basket with a braided band; behind them a half-timbered hall
over a three-bay stone arcade (the waiting hall, open to the market) with a red tile roof and a
bell turret on the ridge to call the hands. Labour-yard family helpers (shared by
rural_daywork_yard, hired_labor_yard, slave_labor_yard): ``union``, ``tint``, ``paste_clipped``,
``shingles``, ``timber``, ``planks``, ``weeds``, ``haft`` (from the hiring fair), ``stones``,
``sack``, ``crate`` (victualling yard), ``wheel``, ``hboards``, ``rope`` (carrier inn); local: ``arcade``, ``frame``,
``hotte``, ``barrow``, ``paving``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 5
REFS = ("guild_hall", "market_warehouse", "construction_center", "market_village")

BASE = 872  # foot of the hall
GROUND = 958  # front edge of the paving (deep enough for the gear to stand clear of the arches)
HX0, HX1 = 120, 744  # hall walls
BAND = 610  # top of the arcade / sill of the timber-framed floor
EAVE, RIDGE = 452, 236
IRON = (40, 38, 36)


# ---------------------------------------------------------------- helpers (labour-yard family finish)
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


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> Image.Image:
    """Squared beam as a polygon: lit upper/left half, darker other half, a lit arris. Returns the mask."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (abs(ny) < 1e-6 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def planks(ic: Icon, pts, c1="#86603e", c2="#4e3522", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
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



def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = False, tall: float = 1.0) -> None:
    """Tuft of grass and weeds."""
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(int(w / 4)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 36) * tall
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(92, 132), R.randint(108, 138), R.randint(48, 66), 235)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)



def haft(ic: Icon, base, top, width: float = 18, wood=("#c9a676", "#7a5834")) -> None:
    """Round ash tool handle: pale, lit on its left edge, darker right, a grime band near the grip."""
    (x0, y0), (x1, y1) = base, top
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L  # normal pointing to the right of the handle
    if nx < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], (min(x0, x1) - h, max(x0, x1) + h), vertical=False, noise=0.12)
    right = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(right), m), (30, 16, 6), 0.35)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 240, 210, 110))
    grip = [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f) for f in (0.55, 0.7)]
    ic.line(grip, int(width), (60, 40, 22, 60))
    ic.outline(pts, 4, (40, 26, 14, 190))




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


def sack(ic: Icon, cx, base, w, h, c=("#a8844e", "#54391c"), lean: float = 0) -> None:
    """Burlap sack: lumpy body slumped wider at the foot, coarse weave, lit from the upper left, a
    pinched neck tied off with twine and a flared tuft."""
    R = ic.random
    ph1, ph2 = R.uniform(0, 6), R.uniform(0, 6)
    pts = []
    for a in np.linspace(0, 2 * math.pi, 56, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.07 * math.sin(3 * a + ph1) + 0.05 * math.sin(5 * a + ph2) + 0.14 * max(s, 0))
        y = base - h * 0.4 + s * h * 0.42 + 0.04 * h * math.sin(4 * a + ph2)
        if s > 0.55:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.28, base - h * 0.72, w * 1.05), noise=0.22, chroma=0.05)

    def weave(d: ImageDraw.ImageDraw) -> None:
        for v in np.arange(cx - w, cx + w, 7):
            d.line([(v, base - h * 1.2), (v + 3, base + 10)], fill=(40, 26, 12, 34), width=2)
        for v in np.arange(base - h * 1.2, base + 10, 7):
            d.line([(cx - w, v), (cx + w, v + 2)], fill=(255, 232, 190, 22), width=2)

    ic.overlay(weave, body)
    for _ in range(4):  # lumps of grain pushing at the cloth
        lx, ly = cx + R.uniform(-0.3, 0.25) * w, base - h * R.uniform(0.25, 0.7)
        r = w * R.uniform(0.12, 0.2)
        tint(ic, ic.mask("ellipse", (lx - r, ly - r * 0.8, lx + r, ly + r * 0.8)), body, (255, 230, 180), 0.14, 8)
        tint(ic, ic.mask("ellipse", (lx - r * 0.2, ly + r * 0.3, lx + r * 1.3, ly + r * 1.3)), body, (20, 10, 2), 0.22, 8)
    tint(ic, ic.mask("ellipse", (cx - w * 0.05, base - h * 0.62, cx + w * 0.85, base + 10)), body, (18, 10, 4), 0.34, 12)
    for f in (-0.2, 0.14):  # slump creases towards the neck
        ic.line([(cx + w * f * 0.5, base - h * 0.8), (cx + w * f * 1.7, base - h * 0.28)], 4, (40, 24, 10, 110))
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.16, base - h * 0.8), (nx - w * 0.06, base - h * 0.96), (nx - w * 0.2, base - h * 1.14),
            (nx - w * 0.04, base - h * 1.08), (nx + w * 0.06, base - h * 1.18), (nx + w * 0.18, base - h * 1.1),
            (nx + w * 0.07, base - h * 0.96), (nx + w * 0.17, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.12, w * 0.45), noise=0.2)
    ic.outline(neck, 3, (46, 30, 14, 170))
    ic.line([(nx - w * 0.1, base - h * 0.95), (nx + w * 0.11, base - h * 0.94)], 9, (44, 28, 14))
    ic.line([(nx - w * 0.09, base - h * 0.965), (nx + w * 0.1, base - h * 0.955)], 3, (170, 136, 86))
    ic.line([(nx + w * 0.1, base - h * 0.94), (nx + w * 0.2, base - h * 0.84)], 4, (60, 40, 20))
    ic.outline(pts, 4, (46, 30, 14, 180))


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


def hboards(ic: Icon, pts, c1="#8a6442", c2="#4e3522", board: float = 24) -> Image.Image:
    """Horizontal boards (cart sides): per-board tone, lit top edge, dark joint below. Returns the mask."""
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
    """Spoked wheel seen from the side: felloes lit top-left, iron tyre, turned hub."""
    k = lambda c: tuple(int(v * tone) for v in c)  # noqa: E731
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78)))
    sw = max(7, int(r * 0.1))
    for i in range(spokes):
        a = 2 * math.pi * i / spokes + 0.25
        p0 = (cx + math.cos(a) * r * 0.16, cy + math.sin(a) * r * 0.16)
        p1 = (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82)
        ic.line([p0, p1], sw + 4, k((46, 30, 18)))
        lit = 0.5 + 0.5 * math.cos(a + 2.4)
        ic.line([p0, p1], sw, k(tuple(int(80 + 70 * lit + c) for c in (20, 0, -26))))
    ic.fill(ring, k((156, 112, 70)), k((58, 38, 22)), radial=(cx - r * 0.6, cy - r * 0.7, r * 2.1), noise=0.16)
    tw = max(6, int(r * 0.09))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=k((52, 50, 50)) + (255,), width=tw))
    ic.overlay(lambda d: d.arc((cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2), 185, 265, fill=(200, 192, 182, 130),
                               width=3))
    hr = r * 0.22
    ic.fill(ic.mask("ellipse", (cx - hr, cy - hr, cx + hr, cy + hr)), k((150, 108, 66)), k((50, 32, 18)),
            radial=(cx - hr * 0.5, cy - hr * 0.6, hr * 2), noise=0.12)
    ic.overlay(lambda d: d.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), outline=(52, 50, 50, 255), width=5))
    ic.draw.ellipse((cx - hr * 0.35, cy - hr * 0.35, cx + hr * 0.35, cy + hr * 0.35), fill=(36, 32, 30, 255))


# ---------------------------------------------------------------- porters' gear
def frame(ic: Icon, base, h, lean=0.0, load: bool = False) -> None:
    """Porter's carrying frame leaning on the wall: two uprights with horns, rungs, a foot shelf and
    leather shoulder straps; optionally with a lashed bale."""
    turn = lambda pts: Icon.rotate(pts, base, lean)  # noqa: E731  (local y up is negative)
    w = 96
    for x in (-w / 2, w / 2):
        timber(ic, *turn([(x, 0), (x * 0.9, -h - 30)]), 20, "#d2b284", "#8a6a44")
    for f in (0.3, 0.62, 0.9):
        timber(ic, *turn([(-w / 2, -h * f), (w / 2, -h * f)]), 15, "#c8a678", "#80603c")
    shelf = turn([(-w / 2 - 14, -2), (w / 2 + 14, -2), (w / 2 + 14, -22), (-w / 2 - 14, -22)])
    ic.poly(shelf, "#c4a274", "#7a5a38", edge=4)
    if load:
        bx, by = turn([(0, -24)])[0]
        crate(ic, bx - w / 2 - 16, by - h * 0.5, bx + w / 2 + 18, by, top=24, c=("#7e5a38", "#422a14"))
        for f in (0.14, 0.36):
            rope(ic, turn([(-w / 2 - 12, -24 - h * f), (w / 2 + 14, -24 - h * f - 4)]), 5)
    for x in (-w * 0.3, w * 0.3):  # straps
        strap = turn([(x, -h * 0.86), (x * 1.3, -h * 0.6), (x * 1.1, -h * 0.28)])
        ic.line(strap, 13, (50, 32, 20))
        ic.line(strap, 8, (120, 78, 46))


def rope(ic: Icon, pts, width: int = 6) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, (176, 146, 100))


def hotte(ic: Icon, cx, base, h) -> None:
    """Tall wicker back-basket in dark red-brown withies, flared at the mouth, a braided band round the
    middle and a thick rim, with a pair of straps."""
    w0, w1 = h * 0.3, h * 0.66
    body = [(cx - w1 / 2, base - h), (cx + w1 / 2, base - h), (cx + w0 / 2, base), (cx - w0 / 2, base)]
    m = ic.poly_mask(body)
    ic.fill(m, "#8e4e32", "#34160c", (cx - w1 / 2, cx + w1 / 2), vertical=False, noise=0.16, chroma=0.05)

    def weave(d: ImageDraw.ImageDraw) -> None:
        for k, y in enumerate(np.arange(base - h + 14, base, 13)):
            for x in np.arange(cx - w1, cx + w1, 22):
                o = 11 if k % 2 else 0
                d.line([(x + o, y), (x + o + 11, y + 2)], fill=(222, 170, 130, 60), width=5)
                d.line([(x + o + 11, y + 2), (x + o + 22, y)], fill=(30, 12, 6, 90), width=5)
        for i in range(-3, 4):
            d.line([(cx + i * w1 / 7, base - h), (cx + i * w0 / 7, base)], fill=(30, 12, 6, 110), width=3)

    ic.overlay(weave, m)
    band_y = base - h * 0.46
    bw = (w0 + w1) / 4 + h * 0.018
    band = [(cx - bw - 5, band_y - 20), (cx + bw + 5, band_y - 20), (cx + bw - 3, band_y + 20), (cx - bw + 3, band_y + 20)]
    bm = ic.poly_mask(band)
    ic.fill(bm, "#c89868", "#5e3620", (cx - bw, cx + bw), vertical=False, noise=0.14)
    ic.overlay(lambda d: [d.line([(x, band_y - 16), (x + 14, band_y + 16)], fill=(40, 18, 8, 170), width=5)
                          for x in np.arange(cx - bw - 20, cx + bw + 10, 15)], bm)
    ic.outline(band, 3, (36, 18, 10, 190))
    tint(ic, ic.mask("rectangle", (cx + w0 * 0.1, base - h, cx + w1, base)), m, (20, 8, 2), 0.35, 12)
    ic.fill(ic.mask("ellipse", (cx - w1 / 2, base - h - 16, cx + w1 / 2, base - h + 16)), "#2a160c", "#120804",
            noise=0.08)
    ic.overlay(lambda d: d.ellipse((cx - w1 / 2, base - h - 16, cx + w1 / 2, base - h + 16), outline=(146, 90, 58, 255),
                                   width=10))
    ic.overlay(lambda d: d.arc((cx - w1 / 2, base - h - 16, cx + w1 / 2, base - h + 16), 150, 260,
                               fill=(214, 164, 120, 160), width=4))
    for x in (-w1 * 0.26, w1 * 0.22):  # shoulder straps hanging down the back
        strap = [(cx + x, base - h + 6), (cx + x * 1.25, base - h * 0.62), (cx + x * 1.1, base - h * 0.2)]
        ic.line(strap, 14, (40, 24, 14))
        ic.line(strap, 8, (150, 104, 64))
    ic.outline(body, 4, (36, 18, 10, 200))


def barrow(ic: Icon, x, base) -> None:
    """Porter's wheelbarrow in side view, facing right: low plank tray on two shafts running down to a
    dark iron-tyred wheel at the nose, long handles rising to the back left, a leg, two burlap sacks."""
    wx, wr = x + 250, 58
    wy = base - wr
    grip = (x - 96, base - 150)

    def shaft(dy: float, tone: float) -> None:
        c1 = tuple(int(v * tone) for v in (176, 134, 88))
        c2 = tuple(int(v * tone) for v in (92, 64, 38))
        timber(ic, (grip[0], grip[1] + dy), (wx + 4, wy + dy), 20, c1, c2)
        g = [(grip[0] - 12, grip[1] + dy - 6), (grip[0] + 34, grip[1] + dy + 10)]
        ic.line(g, 24, (44, 28, 16))
        ic.line(g, 15, tuple(int(v * tone) for v in (186, 148, 100)))

    shaft(-12, 0.62)
    timber(ic, (x + 24, base - 90), (x + 16, base - 4), 18, "#5e4430", "#34220e")  # far leg
    wheel(ic, wx, wy, wr, spokes=8, tone=0.62)
    ic.overlay(lambda d: d.ellipse((wx - wr, wy - wr, wx + wr, wy + wr), outline=(30, 28, 28, 255), width=13))
    ic.overlay(lambda d: d.arc((wx - wr + 3, wy - wr + 3, wx + wr - 3, wy + wr - 3), 190, 262,
                               fill=(170, 164, 156, 170), width=4))
    for a in (200, 290, 20, 110):  # tyre nails
        r = math.radians(a)
        ic.draw.ellipse((wx + math.cos(r) * (wr - 6) - 4, wy + math.sin(r) * (wr - 6) - 4,
                         wx + math.cos(r) * (wr - 6) + 4, wy + math.sin(r) * (wr - 6) + 4), fill=(88, 84, 80, 255))
    tray = [(x - 6, base - 142), (wx + 22, base - 150), (wx - 26, base - 80), (x + 34, base - 84)]
    tm = hboards(ic, tray, "#7a5434", "#3e2614", board=26)
    tint(ic, ic.mask("rectangle", (wx - 80, base - 160, wx + 40, base - 76)), tm, (0, 0, 0), 0.25, 14)
    ic.outline(tray, 5, (40, 26, 16, 190))
    sack(ic, x + 64, base - 124, 128, 84, c=("#ac8850", "#553a1c"), lean=-0.4)
    sack(ic, x + 170, base - 128, 110, 72, c=("#9e7a44", "#4c3216"), lean=0.5)
    ic.line([(x - 10, base - 144), (wx + 26, base - 152)], 12, (104, 74, 46))  # tray rim in front of the sacks
    ic.line([(x - 10, base - 148), (wx + 22, base - 156)], 3, (230, 200, 150, 110))
    shaft(0, 1.0)
    timber(ic, (x + 44, base - 86), (x + 36, base - 2), 20, "#8a6644", "#4a3220")  # near leg


def paving(ic: Icon) -> None:
    """Cobbled market paving before the hall: a strip seen from above with a dark kerb."""
    top = [(10, BASE - 16), (1014, BASE - 16), (1014, GROUND), (10, GROUND)]
    stones(ic, (10, BASE - 16, 1014, GROUND), "#a4927a", "#766550", course=20, lit=50, shadow=110, moss=0.04,
           clip=ic.poly_mask(top))
    stones(ic, (10, GROUND, 1014, GROUND + 22), "#6e5c48", "#48392a", course=32, lit=40, shadow=120, moss=0.1)
    tint(ic, ic.mask("rectangle", (10, GROUND, 1014, GROUND + 10)), None, (0, 0, 0), 0.3, 5)
    ic.outline([(10, BASE - 16), (1014, BASE - 16), (1014, GROUND + 22), (10, GROUND + 22)], 5)
    tint(ic, ic.mask("rectangle", (HX0, BASE - 16, HX1, BASE + 14)), None, (0, 0, 0), 0.4, 10)


# ---------------------------------------------------------------- the hall
def arcade(ic: Icon) -> None:
    """Ground floor: three open round arches on sandstone piers; sacks and crates in the dim hall."""
    wall = ic.mask("rectangle", (HX0, BAND, HX1, BASE))
    stones(ic, (HX0, BAND, HX1, BASE), "#9a866a", "#5e4e3a", course=36, moss=0.05)
    tint(ic, ic.mask("rectangle", (HX1 - 140, BAND, HX1, BASE)), wall, (0, 0, 0), 0.22, 40)
    tint(ic, ic.mask("rectangle", (HX0, BASE - 80, HX1, BASE)), wall, (40, 44, 20), 0.2, 20)
    bays = 3
    bw = (HX1 - HX0) / bays
    for i in range(bays):
        cx = HX0 + bw * (i + 0.5)
        w = bw * 0.66
        x0, x1 = cx - w / 2, cx + w / 2
        spring = 740
        vous = union(ic.mask("ellipse", (x0 - 26, spring - w / 2 - 26, x1 + 26, spring + w / 2 + 26)),
                     ic.mask("rectangle", (x0 - 26, spring, x1 + 26, BASE)))
        ic.fill(vous, "#b09c7c", "#6e5e48", (spring - w / 2 - 26, BASE), noise=0.16)
        ic.overlay(lambda d, cx=cx, w=w: [d.line([(cx + math.cos(a) * w / 2, spring + math.sin(a) * w / 2),
                                                  (cx + math.cos(a) * (w / 2 + 26), spring + math.sin(a) * (w / 2 + 26))],
                                                 fill=(50, 38, 28, 150), width=4)
                                          for a in np.linspace(math.pi, 2 * math.pi, 8)[1:-1]])
        opening = union(ic.mask("ellipse", (x0, spring - w / 2, x1, spring + w / 2)),
                        ic.mask("rectangle", (x0, spring, x1, BASE)))
        ic.fill(opening, "#2a1f16", "#0e0906", (spring - w / 2, BASE), noise=0.1)
        with ic.clipped(opening):
            if i == 0:
                sack(ic, cx - 30, BASE + 2, 100, 100, c=("#6e6450", "#2e281e"))
                sack(ic, cx + 44, BASE + 4, 90, 86, c=("#645a48", "#2a241c"))
            elif i == 1:
                crate(ic, cx - 70, 790, cx + 20, BASE + 4, top=18, c=("#4e3c2a", "#241a12"))
                crate(ic, cx + 10, 816, cx + 80, BASE + 4, top=16, c=("#46362a", "#201810"))
            ic.shade(opening, (0, 0, 0), 0.3)
            tint(ic, ic.mask("rectangle", (x0, spring - w / 2, x1, spring + 20)), None, (0, 0, 0), 0.5, 16)
    ic.outline([(HX0, BAND), (HX1, BAND), (HX1, BASE), (HX0, BASE)], 5)


def upper(ic: Icon) -> None:
    """Timber-framed upper floor: jettied over the arcade, plaster panels, a row of shuttered windows."""
    box = (HX0 - 16, EAVE, HX1 + 16, BAND - 12)
    posts = [HX0 - 4, 250, 380, 486, 616, HX1 + 4]
    ic.plaster_frame(box, posts=posts, braces=(((250, BAND - 12), (318, EAVE)), ((616, BAND - 12), (548, EAVE))),
                     wall="#dccaa4", wall_dark="#b49c76")
    um = ic.mask("rectangle", box)
    for x0 in (140, 290, 406, 510, 650):
        x1 = x0 + 50
        ic.window(x0 + 10, 492, x1 + 10, 556)
        tint(ic, ic.mask("rectangle", (x0, 566, x1 + 24, 584)), um, (0, 0, 0), 0.25, 6)
    for _ in range(8):
        x = ic.random.uniform(HX0, HX1)
        tint(ic, ic.mask("ellipse", (x - 40, 540, x + 40, 620)), um, (90, 60, 30), 0.08, 20)
    tint(ic, ic.mask("rectangle", (HX0 - 16, EAVE, HX1 + 16, EAVE + 60)), um, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (HX1 - 120, EAVE, HX1 + 16, BAND)), um, (0, 0, 0), 0.2, 30)
    ic.rect((HX0 - 26, BAND - 18, HX1 + 26, BAND + 6), "#7a5436", "#48301f")  # jetty beam
    for x in np.linspace(HX0, HX1 - 20, 8):
        ic.rect((x, BAND + 4, x + 18, BAND + 20), "#6a4830", "#3e2818", edge=3)
    tint(ic, ic.mask("rectangle", (HX0, BAND + 6, HX1, BAND + 50)), None, (0, 0, 0), 0.35, 10)


def roof(ic: Icon) -> None:
    """Steep hipped roof of red tiles with a ridge bell turret."""
    pts = [(HX0 - 50, EAVE + 8), (HX0 + 110, RIDGE), (HX1 - 110, RIDGE - 4), (HX1 + 50, EAVE + 8)]
    rm = shingles(ic, pts, "#b8664a", "#6a2c20", course=28, stagger=36, edge=7)
    tint(ic, ic.poly_mask([(HX0 - 60, RIDGE), (360, RIDGE), (260, EAVE + 10), (HX0 - 60, EAVE + 10)]), rm,
         (255, 226, 190), 0.12, 40)
    tint(ic, ic.poly_mask([(520, RIDGE), (HX1 + 60, RIDGE), (HX1 + 60, EAVE + 10), (600, EAVE + 10)]), rm, (0, 0, 0),
         0.22, 40)
    for _ in range(6):  # lichen and soot
        x, y = ic.random.uniform(HX0, HX1), ic.random.uniform(RIDGE + 30, EAVE)
        tint(ic, ic.mask("ellipse", (x - 50, y - 16, x + 50, y + 16)), rm,
             ic.random.choice([(96, 100, 60), (30, 20, 14)]), 0.2, 12)
    ic.line([(HX0 + 108, RIDGE - 2), (HX1 - 108, RIDGE - 6)], 14, (90, 44, 30))
    ic.line([(HX0 + 108, RIDGE - 6), (HX1 - 108, RIDGE - 10)], 4, (220, 160, 130, 110))
    # bell turret
    tx0, tx1, ty0, ty1 = 398, 470, 150, RIDGE + 8
    tm = planks(ic, [(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1)], "#8e6c4a", "#4e3622", board=18)
    tint(ic, ic.mask("rectangle", (tx0 + 40, ty0, tx1, ty1)), tm, (0, 0, 0), 0.3, 6)
    ic.fill(ic.mask("rectangle", (tx0 + 12, ty0 + 14, tx1 - 12, ty0 + 66)), "#1e1610", "#0c0806", noise=0.06)
    bx = (tx0 + tx1) / 2
    bell = [(bx - 14, ty0 + 30), (bx + 14, ty0 + 30), (bx + 22, ty0 + 62), (bx - 22, ty0 + 62)]
    ic.poly(bell, "#b88a48", "#5e4020", edge=3)
    ic.outline([(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1)], 4)
    cap = [(tx0 - 18, ty0 + 4), (bx, 84), (tx1 + 18, ty0 + 4)]
    shingles(ic, cap, "#a86446", "#5e2e20", course=18, stagger=22, edge=5)
    ic.line([(bx, 84), (bx, 58)], 7, IRON)
    ic.draw.ellipse((bx - 7, 50, bx + 7, 64), fill=(60, 56, 52, 255))
    tint(ic, ic.poly_mask([(tx1, RIDGE - 10), (tx1 + 60, RIDGE + 10), (tx1 + 60, RIDGE + 60), (tx1, RIDGE + 40)]), rm,
         (0, 0, 0), 0.3, 10)


def gear(ic: Icon) -> None:
    """Porters' gear before the hall, three separate things standing on the paving: the carrying frame
    with its lashed crate at the left corner, the barrow before the middle arch, the wicker
    back-basket past the right corner. All stay below the arcade springline."""
    fb = GROUND - 10
    tint(ic, ic.mask("ellipse", (0, fb - 24, 160, fb + 14)), None, (0, 0, 0), 0.4, 10)
    frame(ic, (78, fb), 316, lean=4, load=True)
    tint(ic, ic.mask("ellipse", (300, fb - 26, 700, fb + 14)), None, (0, 0, 0), 0.42, 12)
    barrow(ic, 400, fb)
    tint(ic, ic.mask("ellipse", (790, fb - 22, 960, fb + 14)), None, (0, 0, 0), 0.42, 10)
    hotte(ic, 880, fb, 228)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    paving(ic)
    roof(ic)
    upper(ic)
    arcade(ic)
    gear(ic)
    for x in (HX0 + 20, 460, 780):
        weeds(ic, x, BASE - 6, 26, tall=0.6)
