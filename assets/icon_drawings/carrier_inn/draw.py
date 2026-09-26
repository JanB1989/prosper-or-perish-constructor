"""Carrier Inn (carrier_inn): roadside carriers' inn with its yard gate, a covered wagon and a packhorse.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/carrier_inn/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/carrier_inn

Identity: the big arched yard gate with a covered wagon (pale canvas tilt, spoked wheels) standing
in it, and a loaded packhorse waiting on the road in front of the inn. The inn itself is a plain
tiled two-storey house (no sign, no thatch: that is the Tavern). Everything stands on a rutted road.
Transport-family helpers (shared by carrier_inn, transport_office, coastal_shipping_office,
river_boatmen_yard): ``union``, ``tint``, ``paste_clipped``, ``stones``, ``shingles``, ``planks``,
``timber`` (copied from the victualling yard), plus new ``rim``, ``hboards``, ``wheel``, ``cask``,
``crate``, ``sack``, ``rope``; local to this icon: ``wagon``, ``horse``, ``road``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("caravan_stop", "caravanserai", "tambo", "market_village")

GROUND = 936  # where the wagon and the horse stand
BASE = 892  # foot of the inn and the gate wall
L, R = 60, 560  # inn walls
EAVE, RIDGE, BAND = 430, 176, 660
GX0, GX1 = 540, 968  # gate wall
GCX, GRW, GSP = 752, 142, 646  # arch centre x, radius, springing line
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
    xa, xb = min(xs), max(xs)
    span = max(xb - xa, 1)
    sag = course * 0.35  # courses dip a little towards the middle of the plane

    def dip(x: float) -> float:
        return sag * math.sin(math.pi * min(max((x - xa) / span, 0), 1))

    y = min(ys) - course * rnd(0, 0.5)
    while y < max(ys) + course:
        h = course * rnd(0.82, 1.18)
        x = xa - stagger * rnd(0.3, 1.2)  # random, not half-bond, offset per course
        while x < xb:
            w = stagger * rnd(0.6, 1.4)
            dy0, dy1 = dip(x), dip(x + w)
            lip = rnd(-3, 3)
            q = [(x + 2, y + 2 + dy0), (x + w - 2, y + 2 + dy1), (x + w - 2, y + h + dy1 + lip),
                 (x + w / 2, y + h + (dy0 + dy1) / 2 + 4 + lip), (x + 2, y + h + dy0 + lip)]
            t = rnd(-1, 1)
            if ic.random.random() < 0.08:  # the odd replaced or weathered tile
                t = rnd(0.9, 1.6) * (1 if ic.random.random() < 0.5 else -1)
            td.polygon(q, fill=(20, 10, 6, int(min(-t, 1.6) * 62)) if t < 0 else (255, 236, 210, int(min(t, 1.6) * 44)))
            if ic.random.random() < 0.75:
                td.line([(x + w - 2, y + 6 + dy1), (x + w - 2 + rnd(-2, 2), y + h - 4 + dy1)], fill=(40, 22, 14, 70),
                        width=3)
            td.line([(x + 4, y + h - 3 + dy0 + lip), (x + w - 4, y + h - 3 + dy1 + lip)], fill=(255, 232, 205, 52),
                    width=4)
            sd.line([(x, y + h + 4 + dy0 + lip), (x + w, y + h + 4 + dy1 + lip)], fill=255, width=8)
            x += w
        y += h
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


# ---------------------------------------------------------------- the inn
def inn(ic: Icon) -> None:
    # chimney on the ridge
    cx0, cx1, ctop = 150, 214, 112
    cm = ic.mask("rectangle", (cx0, ctop, cx1, RIDGE + 40))
    stones(ic, (cx0, ctop, cx1, RIDGE + 40), "#a89a86", "#6a5e50", course=26)
    tint(ic, ic.mask("rectangle", (cx0 + 36, ctop, cx1 + 10, RIDGE + 40)), cm, (0, 0, 0), 0.32, 10)
    ic.outline([(cx0, ctop), (cx1, ctop), (cx1, RIDGE + 40), (cx0, RIDGE + 40)], 4)
    ic.poly([(cx0 - 10, ctop - 12), (cx1 + 10, ctop - 12), (cx1 + 10, ctop + 8), (cx0 - 10, ctop + 8)],
            "#b4a894", "#7c7264", edge=4)
    # tiled roof, gable end half-hipped on the left, sagging a little
    roof = [(L - 34, EAVE + 14), (L + 44, RIDGE + 20), (L + 70, RIDGE), (340, RIDGE + 6), (R + 4, RIDGE - 2),
            (R + 30, EAVE + 14)]
    rm = shingles(ic, roof, "#b06a4c", "#5e3022", course=30, stagger=40, edge=0)
    tint(ic, ic.poly_mask([(L, RIDGE), (260, RIDGE), (200, EAVE), (L - 40, EAVE)]), rm, (255, 226, 190), 0.12, 40)
    tint(ic, ic.mask("rectangle", (L - 40, EAVE - 44, R + 40, EAVE + 20)), rm, (20, 8, 4), 0.3, 14)
    tint(ic, ic.poly_mask([(cx1, RIDGE + 30), (cx1 + 44, RIDGE + 56), (cx1 + 44, RIDGE + 120), (cx1, RIDGE + 90)]),
         rm, (0, 0, 0), 0.3, 12)
    # ridge tiles
    ridge = [(L + 64, RIDGE - 12), (R + 6, RIDGE - 14), (R + 8, RIDGE + 8), (L + 60, RIDGE + 10)]
    ic.fill(ic.poly_mask(ridge), "#9a5a40", "#5a3020", (RIDGE - 14, RIDGE + 10), noise=0.2)
    ic.overlay(lambda d: [d.arc((x, RIDGE - 14, x + 36, RIDGE + 10), 180, 360, fill=(60, 30, 20, 150), width=3)
                          for x in range(L + 64, R, 34)])
    ic.outline(roof, 6)
    # a dormer in the roof: the carriers' loft
    dx0, dx1, dy0, dy1 = 330, 426, 292, 400
    ic.fill(ic.mask("rectangle", (dx0, dy0 + 30, dx1, dy1)), "#c8b28a", "#8a7456", noise=0.18)
    ic.window(dx0 + 22, dy0 + 46, dx1 - 22, dy1 - 14)
    shingles(ic, [(dx0 - 22, dy0 + 40), ((dx0 + dx1) / 2, dy0 - 20), (dx1 + 22, dy0 + 40), (dx1 + 22, dy0 + 56),
                  ((dx0 + dx1) / 2, dy0 + 2), (dx0 - 22, dy0 + 56)], "#a86448", "#5a2e20", course=16, stagger=22,
             edge=5)
    tint(ic, ic.mask("rectangle", (dx0 - 20, dy1, dx1 + 40, dy1 + 26)), rm, (0, 0, 0), 0.35, 8)
    ic.outline([(dx0, dy0 + 40), (dx1, dy0 + 40), (dx1, dy1), (dx0, dy1)], 4)

    # upper floor: ochre plaster in a timber frame
    ic.plaster_frame((L, EAVE + 14, R, BAND), posts=(L + 12, 196, 330, 440, R - 12),
                     braces=(((330, BAND), (440, EAVE + 14)),), wall="#d8bf8e", wall_dark="#a88a5c")
    up = ic.mask("rectangle", (L, EAVE + 14, R, BAND))
    for x0, y0, x1, y1 in ((100, 496, 156, 580), (236, 494, 290, 578), (476, 498, 526, 578)):
        ic.window(x0, y0, x1, y1)
        tint(ic, ic.mask("rectangle", (x0 - 10, y1 + 10, x1 + 14, y1 + 26)), up, (0, 0, 0), 0.25, 6)
    tint(ic, ic.mask("rectangle", (L, EAVE + 14, R, EAVE + 70)), up, (0, 0, 0), 0.45, 12)
    for _ in range(7):
        x = ic.random.uniform(L, R)
        tint(ic, ic.mask("ellipse", (x - 40, 540, x + 40, 650)), up, (70, 46, 20), 0.12, 20)

    # stone ground floor
    wall = ic.mask("rectangle", (L + 8, BAND, R - 8, BASE))
    stones(ic, (L + 8, BAND, R - 8, BASE), "#a49484", "#665a4c", course=36)
    tint(ic, ic.mask("rectangle", (L, BASE - 80, R, BASE)), wall, (40, 44, 20), 0.22, 22)
    tint(ic, ic.mask("rectangle", (L, BAND, R, BAND + 56)), wall, (0, 0, 0), 0.45, 12)
    ic.rect((L - 12, BAND - 12, R + 10, BAND + 12), "#6e4c32", "#48301f")
    ic.outline([(L + 8, BAND), (R - 8, BAND), (R - 8, BASE), (L + 8, BASE)], 5)
    ic.window(96, 712, 150, 790)
    ic.door(210, 716, 290, BASE - 4)
    ic.window(372, 712, 428, 790)
    for x0, x1 in ((86, 160), (362, 438)):
        tint(ic, ic.mask("rectangle", (x0, 800, x1 + 10, 826)), wall, (0, 0, 0), 0.3, 6)


# ---------------------------------------------------------------- the yard gate
def gate(ic: Icon) -> None:
    top = 470
    wall = ic.mask("rectangle", (GX0, top, GX1, BASE))
    stones(ic, (GX0, top, GX1, BASE), "#aa9a86", "#6c5f50", course=40, moss=0.08)
    tint(ic, ic.mask("rectangle", (GX1 - 90, top, GX1, BASE)), wall, (0, 0, 0), 0.3, 30)
    tint(ic, ic.mask("rectangle", (GX0, BASE - 90, GX1, BASE)), wall, (40, 44, 20), 0.22, 22)
    # voussoirs round the arch
    vr = GRW + 38
    ring = union(ic.mask("ellipse", (GCX - vr, GSP - vr, GCX + vr, GSP + vr)),
                 ic.mask("rectangle", (GCX - vr, GSP, GCX + vr, BASE)))
    ic.fill(ring, "#c2b49c", "#857866", (GSP - vr, BASE), noise=0.16)
    for a in np.linspace(math.pi, 2 * math.pi, 11):
        ic.line([(GCX + math.cos(a) * GRW, GSP + math.sin(a) * GRW), (GCX + math.cos(a) * vr, GSP + math.sin(a) * vr)],
                4, (60, 48, 36, 170))
    for y in np.arange(GSP + 40, BASE, 46):
        for sx in (-1, 1):
            ic.line([(GCX + sx * GRW, y), (GCX + sx * vr, y)], 4, (60, 48, 36, 170))
    tint(ic, ic.mask("rectangle", (GCX + 40, GSP - vr, GCX + vr, BASE)), ring, (0, 0, 0), 0.22, 20)
    ic.overlay(lambda d: d.arc((GCX - vr, GSP - vr, GCX + vr, GSP + vr), 180, 360, fill=(40, 28, 20, 200), width=5))
    # dark gateway with the sunlit yard beyond
    opening = union(ic.mask("ellipse", (GCX - GRW, GSP - GRW, GCX + GRW, GSP + GRW)),
                    ic.mask("rectangle", (GCX - GRW, GSP, GCX + GRW, BASE)))
    ic.fill(opening, "#3a2c1f", "#1e150e", (GSP - GRW, BASE), noise=0.1)
    with ic.clipped(opening):
        # the passage: a boarded back wall under a tie beam, the lit yard through a far opening
        planks(ic, [(GCX - GRW, GSP - GRW), (GCX + GRW, GSP - GRW), (GCX + GRW, BASE), (GCX - GRW, BASE)],
               "#5e4630", "#34261a", 30)
        far = (GCX - 64, 548, GCX + 12, 700)
        ic.fill(ic.mask("rectangle", far), "#c4ae80", "#8a7650", (far[1], far[3]), noise=0.2)
        ic.fill(ic.mask("rectangle", (far[0], 640, far[2], 700)), "#8e7c56", "#6a5a3c", (640, 700), noise=0.25)
        tint(ic, ic.mask("rectangle", (far[0], far[1], far[0] + 22, far[3])), None, (20, 12, 6), 0.45, 6)
        ic.outline([(far[0], far[3]), (far[0], far[1]), (far[2], far[1]), (far[2], far[3])], 4, (40, 28, 18, 200))
        ic.fill(ic.mask("rectangle", (GCX - GRW, BASE - 110, GCX + GRW, BASE)), "#7e6c4c", "#4a3e2c", (780, BASE),
                noise=0.2)
        timber(ic, (GCX - GRW, 540), (GCX + GRW, 548), 22, "#6e5238", "#3e2c1c")
        for x in (GCX - 100, GCX + 40, GCX + 110):
            timber(ic, (x, GSP - GRW), (x + 4, 540), 14, "#5a4230", "#34261a")
        # dusk falls off from the arch edge inwards, strongest high under the vault
        tint(ic, ic.mask("rectangle", (GCX - GRW, GSP - GRW, GCX + GRW, 560)), None, (0, 0, 0), 0.5, 30)
        tint(ic, ic.mask("rectangle", (GCX + 30, GSP - GRW, GCX + GRW, BASE)), None, (0, 0, 0), 0.3, 30)
        tint(ic, ImageChops.subtract(opening, opening.filter(ImageFilter.MinFilter(41))), None, (0, 0, 0), 0.35, 14)
        # gate leaves folded back against the jambs
        for sx in (-1, 1):
            x0 = GCX + sx * GRW
            x1 = GCX + sx * (GRW - 46)
            leaf = [(x0, GSP - 70), (x1, GSP - 40), (x1, 856), (x0, BASE)]
            planks(ic, leaf, "#6e5236", "#3a2a1a", board=16)
            tint(ic, ic.poly_mask(leaf), None, (0, 0, 0), 0.25)
            ic.line([(x0, 700), (x1, 704)], 7, IRON)
            ic.line([(x0, 820), (x1, 818)], 7, IRON)
    ic.outline([(GX0, top), (GX1, top), (GX1, BASE), (GX0, BASE)], 5)
    # gate roof: a short tiled saddle along the wall top, gabled over the arch
    left = [(GX0 - 20, top + 12), (GX0 - 4, top - 34), (GCX, 292), (GCX, 326), (GX0 + 10, top + 12)]
    right = [(GCX, 292), (GX1 + 4, top - 34), (GX1 + 22, top + 12), (GCX, 326)]
    gm = ic.poly_mask([(GX0 + 20, top), (GCX, 330), (GX1 - 20, top)])
    planks(ic, [(GX0 + 20, top + 4), (GCX, 330), (GX1 - 20, top + 4)], "#8c6a48", "#4e3824", board=26)
    tint(ic, ic.mask("rectangle", (GX0, 300, GX1, 400)), gm, (0, 0, 0), 0.4, 20)
    # loft door in the gable, a hoist beam
    ic.rect((GCX - 36, 380, GCX + 36, 462), "#2a1f16", "#120c08", noise=0.1, edge=4)
    timber(ic, (GCX, 346), (GCX, 372), 20)
    ic.outline([(GX0 + 20, top + 4), (GCX, 330), (GX1 - 20, top + 4)], 5)
    shingles(ic, left, "#b06a4c", "#5e3022", course=24, stagger=32, edge=6)
    rr = shingles(ic, right, "#94583e", "#4e281c", course=24, stagger=32, edge=6)
    tint(ic, rr, rr, (0, 0, 0), 0.14)
    ic.rect((GX0 - 24, top, GX1 + 24, top + 16), "#6e4c32", "#48301f", edge=4)


# ---------------------------------------------------------------- wagon
def wagon(ic: Icon) -> None:
    """Carrier's long wagon in profile facing left: canvas tilt on hoops, boarded bed, spoked wheels,
    shafts resting on the road."""
    x0, x1 = 566, 948
    bt, bb = 736, 800  # bed top / bottom
    ht = 586  # hood top
    fw, rw = (648, 860, 74), (870, 846, 90)
    # far wheels peeking out higher and to the left, in shadow
    wheel(ic, fw[0] - 22, fw[1] - 20, fw[2] * 0.96, tone=0.5)
    wheel(ic, rw[0] - 22, rw[1] - 20, rw[2] * 0.96, tone=0.5)
    # far shaft
    timber(ic, (x0 + 30, bb - 26), (402, GROUND - 26), 16, "#5e4430", "#3a2818")
    # undercarriage
    ic.rect((x0 + 40, bb - 6, x1 - 30, bb + 26), "#4a3424", "#2a1c12", edge=4)
    # bed
    bed = [(x0, bt), (x1, bt), (x1 - 8, bb), (x0 + 10, bb)]
    bm = hboards(ic, bed, "#96704a", "#553a24", board=21)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, bt, x1, bb)), bm, (0, 0, 0), 0.22, 30)
    for x in np.linspace(x0 + 24, x1 - 24, 6):
        timber(ic, (x, bt - 2), (x - 4, bb + 2), 14, "#7a5638", "#4a3220")
    ic.outline(bed, 5)
    # canvas tilt over hoops
    n = 5
    hood = [(x0 + 14, bt + 4), (x0 - 6, bt - 46), (x0 - 20, ht + 70), (x0 - 18, ht + 34), (x0 + 6, ht + 10)]
    for t in np.linspace(0, 1, 41):
        x = x0 + 20 + (x1 - x0 - 40) * t
        hood.append((x, ht + 6 - 6 * math.sin(math.pi * t) + 4 * abs(math.sin(math.pi * n * t))))
    hood += [(x1 + 4, ht + 10), (x1 + 24, ht + 34), (x1 + 28, ht + 76), (x1 + 12, bt - 44), (x1 - 6, bt + 4)]
    hm = ic.poly_mask(hood)
    ic.fill(hm, "#e6dac0", "#9a8c70", radial=(x0 + 60, ht - 20, (x1 - x0) * 1.15), noise=0.12, chroma=0.04)
    # cloth folds: lit ridges over each hoop, soft troughs between, all running down the side
    for i in range(n + 1):
        x = x0 + 30 + (x1 - x0 - 60) * i / n
        tint(ic, ic.poly_mask([(x - 8, ht), (x + 8, ht), (x + 12, bt), (x - 6, bt)]), hm, (255, 250, 236), 0.35, 6)
        if i < n:
            xm = x + (x1 - x0 - 60) / n / 2
            tint(ic, ic.poly_mask([(xm - 12, ht + 10), (xm + 12, ht + 10), (xm + 16, bt), (xm - 10, bt)]), hm,
                 (60, 50, 30), 0.3, 10)
    tint(ic, ic.mask("rectangle", (x0 - 30, bt - 50, x1 + 30, bt + 10)), hm, (40, 30, 16), 0.35, 16)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, ht - 10, x1 + 40, bt)), hm, (20, 12, 4), 0.2, 40)
    # the puckered front opening
    fo = ic.mask("ellipse", (x0 - 26, ht + 30, x0 + 36, bt - 10))
    tint(ic, fo, hm, (26, 18, 10), 0.85, 3)
    ic.overlay(lambda d: d.arc((x0 - 26, ht + 30, x0 + 36, bt - 10), 270, 450, fill=(120, 104, 80, 220), width=6), hm)
    for y in np.linspace(ht + 50, bt - 30, 6):  # drawstring gathers
        ic.line([(x0 + 18, y), (x0 + 30, y + 6)], 3, (90, 76, 56, 170))
    # lashing along the bed rail
    for x in np.linspace(x0 + 20, x1 - 20, 14):
        ic.line([(x, bt - 18), (x + 10, bt + 4)], 4, (70, 54, 36, 200))
    rim(ic, hm, 4, (70, 58, 40), 0.6)
    ic.outline(hood, 5)
    # near wheels and shaft
    wheel(ic, *fw)
    wheel(ic, *rw)
    timber(ic, (x0 + 20, bb - 8), (380, GROUND - 6), 18, "#8a6444", "#4e3522")
    ic.line([(470, 880), (480, 900)], 6, IRON)


# ---------------------------------------------------------------- packhorse
def horse(ic: Icon, X: float, G: float, s: float = 1.0, bend: float = 0.3) -> None:
    """Bay packhorse in profile facing left, head lowered, a canvas bale on a pack saddle over a red
    saddle cloth. Lit from the upper left: warm light along neck, back and rump, dark belly and far legs,
    hoof contact shadows on the road."""

    def sm(t: float) -> float:
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def turn(x: float, y: float) -> tuple[float, float]:
        # lower the head and neck: rotate about the withers, fading out over the chest
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

    body_c = ("#a8683a", "#3a1c0a")
    # hoof contact shadows first (the hooves stand on them)
    for hx, hw in ((46, 42), (122, 38), (262, 40), (314, 40)):
        cx = X + (hx + hw / 2) * s
        tint(ic, ic.mask("ellipse", (cx - 34 * s, G - 8 * s, cx + 34 * s, G + 12 * s)), None, (10, 6, 2), 0.6, 5)
    far_fore = P([(100, 200), (112, 120), (122, 64), (124, 26), (122, 0), (160, 0), (154, 24), (150, 64), (146, 120),
                  (156, 200)])
    far_hind = P([(262, 200), (268, 140), (280, 92), (276, 40), (270, 22), (262, 0), (302, 0), (300, 22), (304, 40),
                  (312, 96), (326, 124), (336, 170), (330, 215)])
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
    near_fore = P([(56, 206), (60, 120), (62, 64), (56, 26), (46, 0), (88, 0), (90, 24), (92, 64), (104, 120),
                   (122, 200)])
    near_hind = P([(290, 200), (298, 140), (318, 94), (320, 40), (318, 22), (314, 0), (354, 0), (350, 22), (348, 40),
                   (352, 96), (362, 124), (374, 170), (366, 220)])
    bm = union(ic.poly_mask(body), ic.poly_mask(near_fore), ic.poly_mask(near_hind))
    xs = [p[0] for p in body]
    ic.fill(bm, body_c[0], body_c[1], radial=(min(xs) + 60 * s, G - 420 * s, 480 * s), noise=0.14)
    # modelling: warm light on every upper-left edge (neck crest, back, rump), dark underside and belly
    lit = ImageChops.subtract(bm, ImageChops.offset(bm, int(12 * s), int(26 * s)))
    tint(ic, lit, bm, (255, 208, 150), 0.42, 7 * s)
    under = ImageChops.subtract(bm, ImageChops.offset(bm, int(-6 * s), int(-30 * s)))
    tint(ic, under, bm, (12, 6, 2), 0.5, 10 * s)
    tint(ic, ic.mask("rectangle", (X, G - 196 * s, X + 400 * s, G)), bm, (10, 4, 0), 0.3, 16)
    tint(ic, ic.mask("ellipse", tuple(P([(276, 282)])[0]) + tuple(P([(356, 206)])[0])), bm, (255, 214, 170), 0.26, 14)
    tint(ic, ic.mask("ellipse", tuple(P([(50, 290)])[0]) + tuple(P([(126, 200)])[0])), bm, (255, 214, 170), 0.22, 14)
    tint(ic, ic.mask("ellipse", (X + 150 * s, G - 250 * s, X + 300 * s, G - 150 * s)), bm, (10, 4, 0), 0.25, 18)
    # black points: lower legs, hooves
    tint(ic, ic.mask("rectangle", (X, G - 70 * s, X + 400 * s, G)), bm, (20, 12, 8), 0.7, 8)
    for hx in (46, 314):
        ic.fill(ic.intersect(bm, ic.mask("rectangle", (X + hx * s - 8, G - 16 * s, X + (hx + 44) * s, G + 2))),
                "#4a3e34", "#1a140e", noise=0.1)
    rim(ic, bm, 4, (30, 14, 6), 0.7)
    # mane and forelock
    mane = P([(128, 292), (98, 328), (66, 368), (40, 396), (30, 384), (54, 354), (84, 316), (114, 286)])
    ic.fill(ic.poly_mask(mane), "#2e1c12", "#0e0806", noise=0.2)
    ic.overlay(lambda d: d.line(P([(116, 300), (86, 330), (56, 366)]), fill=(120, 84, 56, 110), width=3))
    ic.poly(P([(30, 398), (38, 428), (50, 400)]), "#9a643a", "#3a2214", edge=3)  # ears
    ic.poly(P([(14, 396), (18, 424), (30, 398)]), "#6a4428", "#2a180c", edge=3)
    ex, ey = P([(4, 366)])[0]
    ic.draw.ellipse((ex - 7, ey - 5, ex + 7, ey + 5), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 5, ey - 4, ex - 1, ey - 1), fill=(190, 180, 170, 255))
    nx, ny = P([(-44, 290)])[0]
    ic.draw.ellipse((nx - 5, ny - 6, nx + 5, ny + 4), fill=(24, 14, 10, 255))
    # halter and lead rope
    ic.line(P([(-34, 312), (-8, 330), (14, 356), (22, 388)]), 6, (70, 40, 24))
    ic.line(P([(-30, 290), (-26, 316)]), 6, (70, 40, 24))
    # saddle cloth, pack saddle, the bale and a rolled bundle on top
    cloth = P([(128, 296), (310, 290), (318, 196), (124, 196)])
    cm = ic.poly_mask(cloth)
    ic.fill(cm, "#c0442a", "#5e180c", (G - 296 * s, G - 196 * s), noise=0.16)
    tint(ic, ic.mask("rectangle", (X + 124 * s, G - 230 * s, X + 320 * s, G - 190 * s)), cm, (20, 4, 0), 0.35, 8)
    ic.overlay(lambda d: d.line(P([(124, 206), (318, 206)]), fill=(214, 176, 96, 210), width=5))
    ic.outline(cloth, 4, (40, 16, 10, 170))
    ic.line(P([(150, 200), (152, 166)]), 12, (70, 46, 28))  # girth
    ic.line(P([(318, 256), (360, 234), (378, 212)]), 9, (70, 46, 28))  # breeching
    bale = P([(146, 212), (140, 290), (150, 336), (190, 350), (268, 350), (300, 336), (308, 290), (302, 214), (260, 204),
              (190, 204)])
    km = ic.poly_mask(bale)
    bx = [p[0] for p in bale]
    ic.fill(km, "#b09c78", "#5e4e36", radial=(min(bx), G - 360 * s, 280 * s), noise=0.16)
    tint(ic, ic.mask("rectangle", (X + 230 * s, G - 360 * s, X + 320 * s, G - 200 * s)), km, (20, 12, 4), 0.3, 16)
    tint(ic, ic.mask("rectangle", (X + 130 * s, G - 250 * s, X + 320 * s, G - 196 * s)), km, (20, 12, 4), 0.45, 12)
    for f in (0.28, 0.72):  # rope ties
        x = X + (146 + 156 * f) * s
        ic.line([(x, G - 350 * s), (x + 4, G - 206 * s)], 7, (84, 62, 38))
    ic.line(P([(142, 280), (306, 276)]), 7, (84, 62, 38))
    ic.outline(bale, 4, (60, 48, 30, 180))
    roll = P([(168, 346), (170, 374), (190, 386), (262, 386), (284, 372), (282, 346)])
    ic.fill(ic.poly_mask(roll), "#6a7a86", "#34404a", (G - 386 * s, G - 346 * s), noise=0.16)
    ic.outline(roll, 4, (30, 34, 40, 180))
    ic.line(P([(226, 348), (226, 386)]), 6, (96, 72, 44))


# ---------------------------------------------------------------- road
def road(ic: Icon) -> None:
    top, bot = BASE - 6, 968
    pts = [(20, top), (1004, top), (1010, bot - 20), (980, bot), (40, bot), (14, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#9a8462", "#6a5638", (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def ruts(d: ImageDraw.ImageDraw) -> None:
        for y in (916, 948):
            x = 20
            while x < 1000:
                ln = rnd(60, 160)
                d.line([(x, y + rnd(-3, 3)), (x + ln, y + rnd(-3, 3))], fill=(50, 36, 20, 120), width=int(rnd(6, 10)))
                d.line([(x, y - 7), (x + ln, y - 7)], fill=(230, 210, 170, 50), width=3)
                x += ln + rnd(10, 50)
        for _ in range(60):
            x, y = rnd(30, 990), rnd(top + 8, bot - 8)
            r = rnd(4, 9)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(210, 196, 170, 140))
            d.line([(x - r, y + r * 0.6), (x + r, y + r * 0.6)], fill=(40, 30, 20, 120), width=2)

    ic.overlay(ruts, m)
    tint(ic, ic.mask("rectangle", (0, top, ic.size, top + 26)), m, (0, 0, 0), 0.35, 10)
    ic.outline(pts, 5)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86
    gate(ic)
    inn(ic)
    road(ic)
    # contact shadows on the road
    tint(ic, ic.mask("ellipse", (560, GROUND - 26, 990, GROUND + 22)), None, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("ellipse", (190, 950 - 20, 580, 950 + 14)), None, (0, 0, 0), 0.4, 12)
    wagon(ic)
    horse(ic, 214, 950, 0.9)
