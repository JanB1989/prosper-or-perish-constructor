"""Victualling Yard (victualling_yard): a Hanseatic brick packhouse with a wall crane and a stack of casks.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/victualling_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/victualling_yard

Identity: the tall crow-stepped brick packhouse with its column of loading doors, the timber wall
crane swinging a slung cask out over the yard, and the pyramid of coopered casks lying end-on in
front. Supporting props: a boarded cooperage shed on the left, salt and biscuit sacks, sealed
crates and stoneware jars (the Packing slot: jars, barrels). No fire (Cookshop), no sign (Tavern).
Local helpers (shared finish with the cookshop): ``union``, ``tint``, ``stones``, ``shingles``,
``crock`` (copied), plus ``timber``/``planks`` (from canal_lock_works) and new ``bricks``,
``cask`` (standing), ``cask_end`` (lying, end-on), ``crate``, ``sack``, ``rope``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 7
REFS = ("market_warehouse", "wharf", "dock", "granary")

BASE = 872  # foot of the walls
GROUND = 918  # where the front props stand on the quay paving
GL, GR = 330, 690  # packhouse gable wall
GEAVE = 392  # height where the crow steps start
WX0, WX1 = 40, GL  # cooperage shed
IRON = (40, 38, 36)


# ---------------------------------------------------------------- helpers (shared food-family finish)
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


def bricks(ic: Icon, m: Image.Image, box, base="#94604a", dark="#5c3a2c", course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:  # over-burnt header
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


def crock(ic: Icon, cx, base, w, h, body=("#a98a6a", "#4a3727"), cloth=("#ddd0b4", "#978667")) -> None:
    """Stoneware crock sealed with a tied cloth: preserved victuals."""
    knots = [(0, 0.30), (0.1, 0.31), (0.2, 0.44), (0.38, 0.5), (0.62, 0.49), (0.9, 0.42), (1.0, 0.37)]
    ss = np.linspace(0, 1, 26)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    ty = base - h
    pts = [(cx - v, ty + h * s) for s, v in zip(ss, hw)] + [(cx + v, ty + h * s) for s, v in zip(ss[::-1], hw[::-1])]
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - w * 0.28, ty + h * 0.4, w * 1.05), noise=0.14)
    tint(ic, ic.mask("rectangle", (cx + w * 0.12, ty, cx + w, base)), m, (20, 12, 6), 0.3, 12)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, ty + h * 0.3, cx - w * 0.2, ty + h * 0.62)), m, (255, 240, 220),
         0.3, 5)
    ic.line([(cx - w * 0.47, ty + h * 0.42), (cx + w * 0.47, ty + h * 0.44)], 3, (60, 40, 24, 120))
    ic.outline(pts, 4, (44, 30, 20, 170))
    lid = [(cx - w * 0.38, ty + h * 0.2), (cx - w * 0.36, ty + h * 0.04), (cx - w * 0.2, ty - h * 0.08),
           (cx + w * 0.02, ty - h * 0.11), (cx + w * 0.24, ty - h * 0.07), (cx + w * 0.37, ty + h * 0.04),
           (cx + w * 0.4, ty + h * 0.22), (cx + w * 0.1, ty + h * 0.16), (cx - w * 0.12, ty + h * 0.23)]
    ic.fill(ic.poly_mask(lid), cloth[0], cloth[1], radial=(cx - w * 0.2, ty - h * 0.08, w * 0.8), noise=0.1)
    ic.outline(lid, 3, (70, 58, 40, 170))
    ic.line([(cx - w * 0.34, ty + h * 0.08), (cx + w * 0.35, ty + h * 0.09)], 5, (92, 62, 38))


def cask(ic: Icon, x0, y0, x1, y1, wood=("#a4764c", "#4c3120"), hoops=(0.14, 0.34, 0.66, 0.86)) -> Image.Image:
    """Standing coopered cask: bulged staves shaded as a cylinder, iron hoops curving with the raised
    camera, lit head on top. Returns the body mask."""
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    bul = w * 0.09
    lip = h * 0.07  # half-height of the head ellipse
    ts = np.linspace(0, 1, 32)
    left = [(x0 - bul * math.sin(math.pi * t), y0 + h * t) for t in ts]
    right = [(x1 + bul * math.sin(math.pi * t), y0 + h * t) for t in ts[::-1]]
    bottom = [(cx + math.cos(a) * w / 2, y1 + math.sin(a) * lip) for a in np.linspace(0, math.pi, 16)]
    pts = left + [(x0, y1)] + bottom[::-1] + [(x1, y1)] + right
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], radial=(x0 + w * 0.3, y0 + h * 0.35, w * 1.05), noise=0.16)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.62, y0 - 10, x1 + bul + 10, y1 + lip + 10)), m, (16, 8, 4), 0.35, 14)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.18, y0 + h * 0.1, x0 + w * 0.34, y1 - h * 0.1)), m, (255, 236, 200),
         0.16, 8)

    def staves(d: ImageDraw.ImageDraw) -> None:
        for f in (0.16, 0.36, 0.58, 0.8):
            x = x0 + w * f
            bend = (x - cx) / (w / 2) * bul
            d.line([(x, y0 + 4), (x + bend, y0 + h / 2), (x, y1)], fill=(44, 26, 14, 70), width=3, joint="curve")

    ic.overlay(staves, m)
    for f in hoops:
        y = y0 + h * f
        b = bul * math.sin(math.pi * f)
        arc = [(cx + math.cos(a) * (w / 2 + b), y + math.sin(a) * lip * 0.9) for a in np.linspace(0, math.pi, 18)]
        ic.line(arc, 10, (58, 54, 52))
        ic.line([(px, py - 3) for px, py in arc[9:]], 3, (170, 160, 150, 120))
    head = (x0 - 1, y0 - lip, x1 + 1, y0 + lip)
    ic.fill(ic.mask("ellipse", head), "#7e5a3a", "#4a3220", (y0 - lip, y0 + lip), noise=0.12)
    inner = (x0 + 8, y0 - lip + 5, x1 - 8, y0 + lip - 4)
    ic.fill(ic.mask("ellipse", inner), "#c49a6c", "#8a6440", radial=(x0 + w * 0.3, y0 - lip, w * 0.9), noise=0.14)
    ic.overlay(lambda d: [d.line([(cx + dx, y0 - lip + 7), (cx + dx, y0 + lip - 6)], fill=(70, 46, 26, 90), width=2)
                          for dx in (-w * 0.2, 0, w * 0.2)])
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def cask_end(ic: Icon, cx, cy, r, depth: float = 0.32, tone: float = 1.0) -> None:
    """Cask lying on its side, seen end-on from the raised camera: the top of the bulged body recedes
    above the head; the head has a chime ring, an iron hoop, boards and a bung."""
    k = lambda c: tuple(int(v * tone) for v in c)  # noqa: E731
    d = r * depth
    body = union(ic.mask("ellipse", (cx - r * 0.98, cy - r * 0.98 - d, cx + r * 0.98, cy + r * 0.98 - d)),
                 ic.mask("rectangle", (cx - r * 0.98, cy - d, cx + r * 0.98, cy)))
    ic.fill(body, k((160, 110, 64)), k((66, 40, 22)), radial=(cx - r * 0.4, cy - r - d, r * 2.2), noise=0.16)
    for f in (0.35, 0.8):  # hoops going round the body behind the head
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
    ic.overlay(lambda dd: dd.arc((cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), 190, 260, fill=(220, 210, 196, 110),
                                 width=4))


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


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        ry = h * 0.42
        y = base - h * 0.42 + s * ry
        if s > 0.6:  # flat where it sits
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    for f in (-0.18, 0.12):
        ic.line([(cx + w * f, base - h * 0.78), (cx + w * f * 1.6, base - h * 0.2)], 3, (70, 58, 40, 90))
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


# ---------------------------------------------------------------- parts
def gable_outline() -> list[tuple[float, float]]:
    """Crow-stepped gable with slightly uneven steps, from the lower left round to the lower right."""
    left = [(GL, BASE), (GL, GEAVE)]
    steps = [(GL, 346), (368, 346), (368, 298), (406, 298), (406, 252), (444, 252), (444, 204), (480, 204),
             (480, 146)]
    left += steps
    right = [(GR + GL - x, y) for x, y in steps[::-1]] + [(GR, GEAVE), (GR, BASE)]
    right = [(x + (3 if y < 300 else 0), y) for x, y in right]
    return left + right


def copings(ic: Icon, outline) -> None:
    """Pale stone copings on every tread of the crow steps, lit on top with a shadow below."""
    for (xa, ya), (xb, yb) in zip(outline, outline[1:]):
        if abs(ya - yb) < 1 and ya < GEAVE and abs(xa - xb) > 10:
            x0, x1 = min(xa, xb) - 6, max(xa, xb) + 6
            ic.rect((x0, ya - 12, x1, ya + 6), "#cdbfa6", "#8c7e6a", edge=4)
            tint(ic, ic.mask("rectangle", (x0 + 6, ya + 6, x1 - 6, ya + 22)), None, (0, 0, 0), 0.35, 5)


def shed(ic: Icon) -> None:
    """Boarded cooperage shed with a pent roof leaning on the packhouse; open door showing casks."""
    ic.fill(ic.mask("rectangle", (WX0 + 10, 470, WX1, 560)), "#4a3a2e", "#2e241c", noise=0.1)  # roof underside
    roof = [(20, 566), (WX1 + 8, 566), (WX1 + 8, 450), (44, 470)]
    rm = shingles(ic, roof, "#98664e", "#553428", course=26, stagger=34, edge=6)
    tint(ic, ic.poly_mask([(WX1 - 90, 440), (WX1 + 10, 440), (WX1 + 10, 570), (WX1 - 60, 570)]), rm, (0, 0, 0), 0.2, 30)
    wall = [(WX0, 566), (WX1, 566), (WX1, BASE), (WX0, BASE)]
    wm = planks(ic, wall, "#86644a", "#46301f", board=30)
    tint(ic, ic.mask("rectangle", (WX0, 566, WX1, 620)), wm, (0, 0, 0), 0.5, 12)  # under the eave
    tint(ic, ic.mask("rectangle", (WX0, BASE - 90, WX1, BASE)), wm, (30, 36, 18), 0.28, 22)  # damp foot
    timber(ic, (WX0 + 4, 572), (WX0 + 4, BASE), 22, "#7c5a3c", "#4a3220")
    timber(ic, (WX0, 578), (WX1, 578), 18, "#7c5a3c", "#4a3220")
    # open door, casks inside in the dark
    dx0, dx1, dy0 = 118, 262, 640
    door = ic.mask("rectangle", (dx0, dy0, dx1, BASE))
    ic.fill(door, "#231a13", "#0e0a07", (dy0, BASE), noise=0.1)
    with ic.clipped(door):
        cask_end(ic, 160, 818, 50, tone=0.55)
        cask_end(ic, 250, 822, 46, tone=0.5)
        cask_end(ic, 204, 740, 46, tone=0.45)
        tint(ic, ic.mask("rectangle", (dx0, dy0, dx1, dy0 + 90)), None, (0, 0, 0), 0.6, 20)
    timber(ic, (dx0 - 8, dy0 - 6), (dx1 + 8, dy0 - 6), 18, "#7c5a3c", "#4a3220")
    for x in (dx0 - 4, dx1 + 4):
        timber(ic, (x, dy0), (x, BASE), 16, "#7c5a3c", "#4a3220")
    # door leaf swung open against the wall
    leaf = [(dx0 - 16, dy0 + 6), (dx0 - 64, dy0 + 20), (dx0 - 64, BASE - 6), (dx0 - 16, BASE)]
    planks(ic, leaf, "#7a5c40", "#44321f", board=16)
    ic.outline(leaf, 4, (40, 26, 16, 170))
    tint(ic, ic.mask("rectangle", (WX1 - 40, 566, WX1 + 10, BASE)), wm, (0, 0, 0), 0.3, 18)
    ic.outline(wall, 5)


def packhouse(ic: Icon) -> None:
    """Tall crow-stepped brick packhouse: roof glimpsed behind the steps, loading doors in a column,
    wall anchors, stone quoins and a stone plinth."""
    out = gable_outline()
    # roof slopes behind the stepped gable, visible in the notches
    roof = [(GL - 6, GEAVE + 4), (515, 132), (GR + 6, GEAVE + 4)]
    shingles(ic, roof, "#6e5c52", "#3c302a", course=24, stagger=30, edge=0)
    gm = ic.poly_mask(out)
    bricks(ic, gm, (GL, 146, GR + 4, BASE), "#a8664a", "#6a3a28")
    # light from the upper left: the right half of the face falls off, grime and soot high up
    tint(ic, ic.mask("rectangle", (560, 100, GR + 30, BASE)), gm, (10, 4, 2), 0.32, 60)
    tint(ic, ic.mask("rectangle", (GL, BASE - 110, GR, BASE)), gm, (30, 30, 16), 0.3, 26)
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(14):
        x = ic.random.uniform(GL + 10, GR - 10)
        y = ic.random.uniform(200, 420)
        sd.line([(x, y), (x + ic.random.uniform(-3, 3), y + ic.random.uniform(60, 180))], fill=255,
                width=int(ic.random.uniform(5, 12)))
    tint(ic, streaks, gm, (34, 22, 16), 0.2, 5)
    for _ in range(12):  # weathered patches: soot, faded brick, a little lichen
        x, y = ic.random.uniform(GL, GR), ic.random.uniform(160, BASE)
        r = ic.random.uniform(30, 70)
        col = ic.random.choice([(20, 10, 6), (240, 200, 160), (96, 100, 60)])
        tint(ic, ic.mask("ellipse", (x - r * 1.2, y - r * 0.7, x + r * 1.2, y + r * 0.7)), gm, col,
             ic.random.uniform(0.08, 0.16), 16)
    # stone quoins at both corners
    for x0, x1 in ((GL, GL + 34), (GR - 34, GR)):
        y, k = GEAVE, 0
        while y < BASE - 70:
            w = (34 if k % 2 else 22) + ic.random.uniform(-3, 3)
            h = ic.random.uniform(27, 34)
            bx = (x0, y, x0 + w, y + h) if x0 == GL else (x1 - w, y, x1, y + h)
            t = ic.random.uniform(0.84, 1.0)
            ic.rect(bx, tuple(int(v * t) for v in (192, 176, 150)), tuple(int(v * t) for v in (132, 118, 98)), edge=0)
            if ic.random.random() < 0.3:  # weathered, grimy block
                ic.shade(ic.mask("rectangle", bx), (50, 44, 30), 0.25)
            ic.line([(bx[0], bx[3]), (bx[2], bx[3])], 4, (40, 28, 20, 150))
            ic.line([(bx[0] + 2, bx[1] + 3), (bx[2] - 2, bx[1] + 3)], 3, (255, 244, 224, 70))
            ic.line([(bx[2] - 2, bx[1] + 3), (bx[2] - 2, bx[3] - 2)], 3, (40, 28, 20, 90))
            y += h + 2
            k += 1
    tint(ic, ic.mask("rectangle", (GR - 34, GEAVE, GR, BASE)), gm, (0, 0, 0), 0.2, 6)
    copings(ic, out)
    # stone plinth
    stones(ic, (GL, BASE - 70, GR, BASE), "#9a8e7e", "#62584c", course=34, moss=0.1)

    # loading doors stacked in the middle column, each under a timber lintel
    cx = 515
    for y0, y1, w in ((196, 262, 50), (330, 420, 74), (500, 590, 76)):
        x0, x1 = cx - w / 2, cx + w / 2
        ic.rect((x0 - 10, y0 - 10, x1 + 10, y1 + 6), "#a89c88", "#6e6454", edge=4)  # stone surround
        ic.fill(ic.mask("rectangle", (x0, y0, x1, y1)), "#2a1e16", "#120c08", (y0, y1), noise=0.1)
        tint(ic, ic.mask("rectangle", (x0, y0, x1, y0 + 26)), None, (0, 0, 0), 0.5, 8)
        # half door leaf folded back on the right
        leaf = [(x1 + 2, y0 + 4), (x1 + 26, y0 + 12), (x1 + 26, y1 + 2), (x1 + 2, y1 - 2)]
        planks(ic, leaf, "#7c5a3a", "#44301e", board=12)
        ic.outline(leaf, 3, (40, 26, 16, 170))
        timber(ic, (x0 - 16, y0 - 14), (x1 + 16, y0 - 14), 14, "#7c5a3c", "#4a3220")
        tint(ic, ic.mask("rectangle", (x0 - 10, y1 + 6, x1 + 30, y1 + 30)), gm, (0, 0, 0), 0.3, 8)
    # small barred windows, deliberately off the grid
    for x0, y0, x1, y1 in ((388, 440, 430, 494), (604, 430, 642, 482), (386, 618, 428, 670), (606, 610, 644, 662),
                           (505, 146 + 14, 526, 178)):
        ic.rect((x0 - 7, y0 - 7, x1 + 7, y1 + 7), "#a89c88", "#6e6454", edge=3)
        ic.rect((x0, y0, x1, y1), "#2c2a2a", "#161414", noise=0.06, edge=0)
        for f in (0.33, 0.66):
            ic.line([(x0 + (x1 - x0) * f, y0), (x0 + (x1 - x0) * f, y1)], 4, (80, 76, 72))
        tint(ic, ic.mask("rectangle", (x0, y0, x1, y0 + 12)), None, (0, 0, 0), 0.4, 4)
    # iron wall anchors
    for x, y in ((372, 360), (656, 356), (372, 560), (660, 548)):
        ic.line([(x - 10, y - 16), (x + 2, y), (x - 6, y + 18)], 7, IRON)
    # ground-floor cart door, arched, open onto a dark interior
    dx0, dx1, dy0 = 450, 590, 694
    w = dx1 - dx0
    arch = union(ic.mask("ellipse", (dx0 - 22, dy0 - 22, dx1 + 22, dy0 + w + 22)),
                 ic.mask("rectangle", (dx0 - 22, dy0 + w / 2, dx1 + 22, BASE)))
    ic.fill(arch, "#bcae96", "#7e7262", (dy0 - 22, BASE), noise=0.16)
    ic.overlay(lambda d: [d.line([((dx0 + dx1) / 2 + math.cos(a) * w / 2, dy0 + w / 2 + math.sin(a) * w / 2),
                                  ((dx0 + dx1) / 2 + math.cos(a) * (w / 2 + 22), dy0 + w / 2 + math.sin(a) * (w / 2 + 22))],
                                 fill=(40, 30, 22, 150), width=4) for a in np.linspace(math.pi, 2 * math.pi, 7)[1:-1]])
    opening = union(ic.mask("ellipse", (dx0, dy0, dx1, dy0 + w)), ic.mask("rectangle", (dx0, dy0 + w / 2, dx1, BASE)))
    ic.fill(opening, "#261c14", "#0e0906", (dy0, BASE), noise=0.1)
    with ic.clipped(opening):
        crate(ic, 470, 810, 560, BASE + 4, top=20, c=("#5a4430", "#2e2218"))
        ic.shade(opening, (0, 0, 0), 0.35)
        tint(ic, ic.mask("rectangle", (dx0, dy0, dx1, dy0 + 70)), None, (0, 0, 0), 0.5, 16)
    ic.outline(out, 6)


def crane(ic: Icon) -> None:
    """Timber wall crane hung on the right corner: post, jib and strut, a sheave, and a slung cask."""
    px = GR + 16
    tint(ic, ic.mask("rectangle", (GR - 8, 300, GR + 4, 560)), None, (0, 0, 0), 0.3, 8)
    timber(ic, (px, 262), (px, 566), 26, "#8a6444", "#4e3522")
    for y in (292, 540):  # iron pintles into the wall
        ic.rect((GR - 6, y - 7, px - 6, y + 7), "#4a4644", "#2a2826", edge=3)
    jx = 918
    timber(ic, (px - 12, 276), (jx, 262), 26, "#8e6646", "#523823")
    timber(ic, (px + 4, 512), (806, 278), 20, "#86603e", "#4c3420")
    ic.line([(px + 2, 262), (jx - 20, 250)], 3, (255, 225, 180, 60))
    # sheave at the jib head
    sx, sy = jx - 16, 290
    ic.ellipse((sx - 20, sy - 20, sx + 20, sy + 20), "#6a625c", "#2e2a28", edge=4)
    ic.draw.ellipse((sx - 5, sy - 5, sx + 5, sy + 5), fill=(30, 28, 26, 255))
    # hoist rope from the jib back to the wall, and down to the cask
    rope(ic, [(sx + 14, sy + 4), (sx + 16, 468)])
    rope(ic, [(sx - 18, sy - 4), (px + 20, 312), (px + 14, 470)], 5)
    # slung cask swinging slightly
    bx, by = sx + 16, 470
    c0, c1, t0, t1 = bx - 46, bx + 44, 500, 596
    rope(ic, [(bx, by), (c0 + 6, t0 + 4)], 5)
    rope(ic, [(bx, by), (c1 - 6, t0 + 4)], 5)
    ic.draw.ellipse((bx - 9, by - 9, bx + 9, by + 9), outline=IRON + (255,), width=5)
    cask(ic, c0, t0, c1, t1)
    rope(ic, [(c0 - 2, t0 + 22), (c0 + 20, t0 + 30), (c1 - 20, t0 + 30), (c1 + 2, t0 + 22)], 4)


def quay(ic: Icon) -> None:
    """Paved quay the yard stands on: lit paving seen from above, a darker kerb face."""
    top = [(12, BASE - 10), (1012, BASE - 10), (1012, GROUND + 14), (12, GROUND + 14)]
    stones(ic, (12, BASE - 10, 1012, GROUND + 14), "#a08a6c", "#766450", course=20, lit=50, shadow=110, moss=0.04,
           clip=ic.poly_mask(top))
    stones(ic, (12, GROUND + 14, 1012, GROUND + 40), "#76604a", "#4a3a2c", course=38, lit=40, shadow=120, moss=0.12)
    tint(ic, ic.mask("rectangle", (12, GROUND + 14, 1012, GROUND + 30)), None, (0, 0, 0), 0.3, 6)
    ic.outline([(12, BASE - 10), (1012, BASE - 10), (1012, GROUND + 40), (12, GROUND + 40)], 5)
    tint(ic, ic.mask("rectangle", (20, BASE - 10, 1004, BASE + 14)), None, (0, 0, 0), 0.4, 10)  # wall contact


def casks_stack(ic: Icon) -> None:
    """Pyramid of casks lying end-on, chocked, with contact shadows between the rows."""
    r = 52
    rows = [
        [(700, GROUND - r - 2), (806, GROUND - r), (913, GROUND - r - 1)],
        [(754, GROUND - 3 * r + 4), (860, GROUND - 3 * r + 6)],
        [(806, GROUND - 5 * r + 12)],
    ]
    tint(ic, ic.mask("ellipse", (620, GROUND - 40, 1000, GROUND + 26)), None, (0, 0, 0), 0.45, 14)
    for i, row in enumerate(rows):
        for cx, cy in row:
            cask_end(ic, cx + ic.random.uniform(-3, 3), cy, r * ic.random.uniform(0.96, 1.03),
                     tone=ic.random.uniform(0.88, 1.06))
        if i + 1 < len(rows):  # the next row shades this one where it rests
            for cx, cy in rows[i + 1]:
                tint(ic, ic.mask("ellipse", (cx - r * 1.2, cy + r * 0.3, cx + r * 1.2, cy + r * 1.6)), None,
                     (0, 0, 0), 0.3, 12)
    # chock wedge at the base
    ic.poly([(634, GROUND), (660, GROUND - 26), (668, GROUND)], "#8a6444", "#4e3522", edge=4)


def front_left(ic: Icon) -> None:
    """Salt and biscuit sacks and sealed crates before the shed."""
    tint(ic, ic.mask("ellipse", (10, GROUND - 40, 330, GROUND + 26)), None, (0, 0, 0), 0.45, 14)
    crate(ic, 214, 806, 338, GROUND, top=26)
    crate(ic, 236, 734, 322, 784, top=22, c=("#94704a", "#56391f"))
    tint(ic, ic.mask("rectangle", (214, 790, 338, 830)), None, (0, 0, 0), 0.3, 8)  # top crate shades the lower
    sack(ic, 150, GROUND + 2, 88, 96, c=("#c8a674", "#6e5230"), lean=0.3)  # ship's biscuit
    sack(ic, 76, GROUND, 104, 118, c=("#dcd6c8", "#86806e"))  # salt


def front_mid(ic: Icon) -> None:
    """Packing goods at the door: stoneware jars and a standing cask."""
    tint(ic, ic.mask("ellipse", (330, GROUND - 30, 640, GROUND + 24)), None, (0, 0, 0), 0.4, 12)
    cask(ic, 346, 790, 426, GROUND - 4, wood=("#9c6e46", "#48301e"))
    crock(ic, 470, GROUND, 74, 96, body=("#a4866a", "#46342a"))
    crock(ic, 534, GROUND + 2, 60, 76, body=("#8e7662", "#3c2e24"), cloth=("#ccc0a4", "#8a7c62"))
    cask(ic, 586, 820, 646, GROUND, wood=("#a87a50", "#4e3420"))


def pennant(ic: Icon) -> None:
    """Iron finial on the top step flying a long swallow-tailed pennant (the yard serves the fleet)."""
    x, y0, y1 = 512, 150, 40
    ts = np.linspace(0, 1, 24)
    top = [(x + 8 + 150 * t, y1 + 6 + 18 * t + 10 * math.sin(math.pi * 2 * t)) for t in ts]
    bot = [(x + 8 + 136 * t, y1 + 40 - 6 * t + 10 * math.sin(math.pi * 2 * t + 0.4)) for t in ts]
    tail = [(top[-1][0] + 20, top[-1][1] + 4), (top[-1][0] - 12, (top[-1][1] + bot[-1][1]) / 2 + 2),
            (bot[-1][0] + 24, bot[-1][1] + 6)]
    pts = top + tail + bot[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, "#b0503a", "#5e2418", (x, x + 170), vertical=False, noise=0.12)
    tint(ic, ic.mask("rectangle", (x + 40, 0, x + 90, 200)), m, (0, 0, 0), 0.25, 16)
    tint(ic, ic.mask("rectangle", (x + 100, 0, x + 130, 200)), m, (255, 220, 190), 0.12, 10)
    ic.outline(pts, 4, (50, 22, 14, 170))
    ic.line([(x, y0), (x, y1 - 10)], 8, IRON)
    ic.line([(x - 2, y0), (x - 2, y1)], 2, (150, 140, 130, 150))
    ic.draw.ellipse((x - 9, y1 - 22, x + 9, y1 - 4), fill=(60, 56, 52, 255))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    pennant(ic)
    shed(ic)
    packhouse(ic)
    quay(ic)
    crane(ic)
    front_left(ic)
    front_mid(ic)
    casks_stack(ic)
