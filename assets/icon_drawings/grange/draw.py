"""Grange (grange): a manorial grange barn with its cart porch open and a loaded wagon leaving for market.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/grange/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/grange

Identity: the huge steep tiled roof of a buttressed stone tithe barn with a vent louvre on the
ridge, a gabled cart porch (midstrey) in front with its tall plank doors swung open onto a dark
threshing floor stacked with sacks, and an open four-wheeled farm wagon piled with grain sacks and
a cask pulling away to the right (overland haulage, the Victualling Yard's inland twin). No water,
no crane, no brick (Victualling Yard), no sign or thatch (Tavern), no stilts or grain heap (vanilla
granary). Helpers copied so the food and transport families share one finish: ``union``, ``tint``,
``paste_clipped``, ``stones``, ``shingles``, ``timber``, ``planks`` (victualling yard), ``hboards``,
``rim``, ``wheel`` (carrier inn), ``cask`` (victualling yard), ``profile``, ``grain_sack`` (public
kitchen), ``sack`` (victualling yard), ``rope``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 13
REFS = ("granary", "local_estates", "farming_village", "market_village")

BASE = 872  # foot of the barn walls
L, R = 30, 744  # barn walls
EAVE, RIDGE = 622, 170
PX0, PX1 = 176, 454  # cart porch
PCX = (PX0 + PX1) / 2
PAPEX, PEAVE, PBASE = 350, 592, 890
DX0, DX1, DTOP = 210, 420, 636  # porch doorway
G = 948  # where the wagon wheels stand
STONE = ("#b4a68c", "#77695a")
TILE = ("#a05e40", "#4a2818")
IRON = (40, 38, 36)


# ---------------------------------------------------------------- helpers (shared finish)
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
    L_ = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L_, (x1 - x0) / L_
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
    R_ = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R_.uniform(0.8, 1.2)
        t = R_.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R_.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R_.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def hboards(ic: Icon, pts, c1="#8a6442", c2="#4e3522", board: float = 24) -> Image.Image:
    """Horizontal boards (cart sides): per-board tone, lit top edge, dark joint below."""
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
            gy = y + rnd(4, max(h - 4, 5))
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
        lit = 0.5 + 0.5 * math.cos(a + 2.4)
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
    """Standing coopered cask: bulged staves shaded as a cylinder, iron hoops curving with the raised
    camera, lit head on top. Returns the body mask."""
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    bul = w * 0.09
    lip = h * 0.07
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


def profile(cx, top, h, w, knots, n=28):
    """Closed outline of a turned form from (s, half-width fraction) knots, s = 0 at the top."""
    ss = np.linspace(0, 1, n)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    return [(cx - v, top + h * s) for s, v in zip(ss, hw)] + [(cx + v, top + h * s) for s, v in zip(ss[::-1], hw[::-1])]


def grain_sack(ic: Icon, cx, base, w, h, open_top=False, col=("#d9c496", "#6e5a3a")) -> Image.Image:
    """Burlap sack, lumpy and lit upper left; either tied at the neck or rolled open showing grain."""
    top = base - h
    if open_top:
        knots = [(0, 0.40), (0.1, 0.45), (0.5, 0.52), (0.85, 0.5), (1, 0.46)]
    else:
        knots = [(0, 0.16), (0.08, 0.2), (0.16, 0.13), (0.3, 0.36), (0.6, 0.5), (0.9, 0.5), (1, 0.44)]
    pts = profile(cx, top, h, w, knots, 30)
    pts = [(x + ic.random.uniform(-2, 2), y + ic.random.uniform(-2, 2)) for x, y in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, col[0], col[1], radial=(cx - w * 0.28, top + h * 0.35, w * 1.0), noise=0.12, chroma=0.05)
    tint(ic, ic.mask("rectangle", (cx + w * 0.1, top, cx + w, base)), m, (20, 12, 4), 0.3, 16)
    folds = Image.new("L", (ic.size, ic.size), 0)
    fd = ImageDraw.Draw(folds)
    for f in (-0.22, 0.05, 0.28):
        x = cx + w * f
        fd.line([(x, top + h * 0.35), (x + w * 0.06, base - h * 0.08)], fill=255, width=6)
    tint(ic, folds, m, (40, 26, 12), 0.3, 5)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.14, cx + w, base + 4)), m, (20, 12, 4), 0.35, 8)
    ic.outline(pts, 4, (60, 44, 26, 180))
    if open_top:
        rim_ = (cx - w * 0.44, top - h * 0.1, cx + w * 0.44, top + h * 0.12)
        ic.fill(ic.mask("ellipse", rim_), "#e2cfa2", "#8a7450", (rim_[1], rim_[3]), noise=0.2)
        heap = [(cx + math.cos(a) * w * 0.38, top + 2 + math.sin(a) * h * 0.2) for a in np.linspace(math.pi, 2 * math.pi, 20)]
        ic.fill(ic.poly_mask(heap), "#f0cc70", "#9a6e24", radial=(cx - w * 0.15, top - h * 0.18, w * 0.6), noise=0.35)
        ic.outline(heap, 3, (110, 76, 24, 150))
    else:
        ic.line([(cx - w * 0.17, top + h * 0.14), (cx + w * 0.17, top + h * 0.15)], 6, (84, 60, 34))
    return m


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack lying slumped: round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        ry = h * 0.42
        y = base - h * 0.42 + s * ry
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    for f in (-0.18, 0.12):
        ic.line([(cx + w * f, base - h * 0.78), (cx + w * f * 1.6, base - h * 0.2)], 3, (70, 58, 40, 90))
    ic.outline(pts, 4, (56, 44, 30, 160))


def rope(ic: Icon, pts, width: int = 6) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, (176, 146, 100))


# ---------------------------------------------------------------- parts
def barn_walls(ic: Icon) -> Image.Image:
    """Long rubble-stone barn wall with ventilation slits and stepped buttresses."""
    wm = ic.mask("rectangle", (L, EAVE, R, BASE))
    stones(ic, (L, EAVE, R, BASE), STONE[0], STONE[1], course=36, moss=0.08)
    tint(ic, ic.mask("rectangle", (L, BASE - 110, R, BASE)), wm, (40, 44, 20), 0.26, 26)  # damp, green foot
    tint(ic, ic.mask("rectangle", (R - 150, EAVE, R + 40, BASE)), wm, (0, 0, 0), 0.2, 40)
    # tall ventilation slits with dressed surrounds
    for x, y0, y1 in ((78, 690, 810), (578, 688, 812)):
        ic.rect((x - 16, y0 - 12, x + 16, y1 + 10), "#c8baa0", "#8a7c66", edge=3)
        ic.rect((x - 7, y0, x + 7, y1), "#241a14", "#0e0a08", noise=0.08, edge=0)
        tint(ic, ic.mask("rectangle", (x - 16, y1 + 10, x + 22, y1 + 28)), wm, (0, 0, 0), 0.3, 6)
    # streaks of grime running down from the eave
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(16):
        x = ic.random.uniform(L + 10, R - 10)
        sd.line([(x, EAVE), (x + ic.random.uniform(-4, 4), EAVE + ic.random.uniform(50, 150))], fill=255,
                width=int(ic.random.uniform(4, 10)))
    tint(ic, streaks, wm, (34, 26, 16), 0.2, 4)
    return wm


def buttress(ic: Icon, x: float, w: float = 40, top: float = EAVE + 40) -> None:
    """Stepped buttress: lit left face, shaded right face, sloped weathering at each step."""
    for (y0, y1, ww) in ((top, top + 100, w * 0.75), (top + 100, BASE + 6, w)):
        box = (x - ww / 2, y0, x + ww / 2, y1)
        m = ic.mask("rectangle", box)
        stones(ic, box, "#c0b298", "#7e705e", course=26, lit=60, shadow=110, moss=0.1)
        tint(ic, ic.mask("rectangle", (x + ww * 0.1, y0, x + ww, y1)), m, (0, 0, 0), 0.28, 6)
        cap = [(x - ww / 2 - 4, y0 + 4), (x + ww / 2 + 4, y0 + 4), (x + ww / 2 + 4, y0 - 12), (x - ww / 2 - 4, y0 - 12)]
        ic.poly([(x - ww / 2 - 4, y0 + 6), (x + ww / 2 + 4, y0 + 6), (x + ww / 2 - 2, y0 - 14), (x - ww / 2 + 2, y0 - 14)],
                "#d4c6aa", "#968a74", edge=3)
        del cap
        ic.outline([(x - ww / 2, y0), (x - ww / 2, y1), (x + ww / 2, y1), (x + ww / 2, y0)], 4)
    tint(ic, ic.mask("rectangle", (x + w / 2, top, x + w / 2 + 30, BASE)), None, (0, 0, 0), 0.3, 8)


def barn_roof(ic: Icon) -> Image.Image:
    """Huge steep hipped roof of weathered clay tiles, sagging slightly, moss and lichen patches."""
    roof = [(4, EAVE + 22), (770, EAVE + 22), (646, RIDGE + 2), (392, RIDGE + 10), (132, RIDGE)]
    rm = shingles(ic, roof, TILE[0], TILE[1], course=27, stagger=36, edge=7)
    for _ in range(34):
        x, y = ic.random.uniform(30, 750), ic.random.uniform(RIDGE, EAVE)
        r = ic.random.uniform(20, 70)
        col = ic.random.choice([(0, 0, 0), (0, 0, 0), (255, 232, 200), (84, 96, 46), (84, 96, 46), (176, 150, 70),
                                (120, 110, 96)])
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), rm, col,
             ic.random.uniform(0.08, 0.2), 14)
    # light from the upper left: the left hip catches it, the right falls off
    tint(ic, ic.poly_mask([(4, EAVE + 22), (132, RIDGE), (300, RIDGE), (200, EAVE + 22)]), rm, (255, 228, 190), 0.14, 50)
    tint(ic, ic.poly_mask([(540, RIDGE), (790, RIDGE), (790, EAVE + 24), (620, EAVE + 24)]), rm, (0, 0, 0), 0.22, 50)
    # hip ridges
    for p0, p1 in (((6, EAVE + 20), (134, RIDGE)), ((768, EAVE + 20), (644, RIDGE + 2))):
        ic.line([p0, p1], 16, (110, 66, 48))
        ic.line([(p0[0] + 4, p0[1] - 6), (p1[0] + 4, p1[1] + 2)], 4, (220, 170, 140, 90))
    ridge = [(126, RIDGE - 12), (392, RIDGE - 4), (652, RIDGE - 10), (652, RIDGE + 8), (392, RIDGE + 16), (126, RIDGE + 8)]
    ic.poly(ridge, "#8e5a44", "#5a3626", edge=4)
    tint(ic, ic.mask("rectangle", (0, EAVE - 30, 790, EAVE + 24)), rm, (30, 14, 6), 0.3, 12)
    return rm


def louvre(ic: Icon, rm: Image.Image) -> None:
    """Little boarded vent louvre astride the ridge with its own tiled cap."""
    x0, x1, top = 540, 636, 96
    tint(ic, ic.poly_mask([(x1, top + 50), (x1 + 60, top + 90), (x1 + 60, RIDGE + 70), (x1, RIDGE + 34)]), rm,
         (0, 0, 0), 0.4, 10)
    body = [(x0, top + 44), (x1, top + 44), (x1, RIDGE + 14), (x0, RIDGE + 14)]
    planks(ic, body, "#9a7a58", "#54402c", board=16)
    ic.rect((x0 + 12, top + 56, x1 - 12, RIDGE + 4), "#241a14", "#0e0a08", noise=0.08, edge=0)  # louvred opening
    for y in np.arange(top + 62, RIDGE, 13):  # slanted slats
        ic.line([(x0 + 12, y), (x1 - 12, y + 5)], 6, (120, 92, 62))
        ic.line([(x0 + 12, y + 4), (x1 - 12, y + 9)], 2, (30, 20, 12))
    ic.outline(body, 4)
    cap = [(x0 - 20, top + 52), ((x0 + x1) / 2, top), (x1 + 20, top + 52)]
    ic.poly(cap, "#9a5e46", "#5a3424", edge=4)
    tint(ic, ic.poly_mask([((x0 + x1) / 2, top), (x1 + 16, top + 38), ((x0 + x1) / 2, top + 52)]), None, (0, 0, 0),
         0.25)


def porch(ic: Icon) -> None:
    """Gabled cart porch (midstrey): boarded gable with a pitching hole, stone jambs, the great doors
    swung open on a dark threshing floor with stacked sacks, and both roof slopes seen from above."""
    # shadow the porch throws on the barn wall to its right
    tint(ic, ic.mask("rectangle", (PX1, EAVE + 30, PX1 + 60, BASE)), None, (0, 0, 0), 0.35, 14)
    # gable triangle: vertical weatherboarding
    gable = [(PX0 + 6, PEAVE + 4), (PX1 - 6, PEAVE + 4), (PCX, PAPEX + 34)]
    gm = planks(ic, gable, "#9a7a58", "#5a4230", board=24)
    tint(ic, ic.mask("rectangle", (PX0, PAPEX, PX1, PAPEX + 130)), gm, (0, 0, 0), 0.4, 20)
    tint(ic, ic.mask("rectangle", (PCX + 30, PAPEX, PX1, PEAVE)), gm, (0, 0, 0), 0.18, 20)
    # pitching hole
    hx0, hx1, hy0, hy1 = PCX - 28, PCX + 28, 470, 540
    ic.rect((hx0 - 10, hy0 - 10, hx1 + 10, hy1 + 6), "#6e4e34", "#43301e", edge=4)
    ic.rect((hx0, hy0, hx1, hy1), "#221812", "#0c0806", noise=0.1, edge=0)
    tint(ic, ic.mask("rectangle", (hx0, hy0, hx1, hy0 + 20)), None, (0, 0, 0), 0.5, 6)
    # porch walls with the great doorway
    wall = ic.mask("rectangle", (PX0, PEAVE, PX1, PBASE))
    stones(ic, (PX0, PEAVE, PX1, PBASE), "#bcae94", "#7c6e5c", course=34, moss=0.06)
    tint(ic, ic.mask("rectangle", (PX0, PBASE - 100, PX1, PBASE)), wall, (40, 44, 20), 0.24, 22)
    tint(ic, ic.mask("rectangle", (PX1 - 50, PEAVE, PX1 + 20, PBASE)), wall, (0, 0, 0), 0.22, 20)
    ic.beam((PX0 - 6, PEAVE + 4), (PX1 + 6, PEAVE + 4), 20, (104, 72, 46))  # tie beam
    tint(ic, ic.mask("rectangle", (PX0, PEAVE + 14, PX1, PEAVE + 60)), wall, (0, 0, 0), 0.4, 10)
    opening = ic.mask("rectangle", (DX0, DTOP, DX1, PBASE))
    ic.fill(opening, "#2a1e16", "#0e0a07", (DTOP, PBASE), noise=0.1)
    with ic.clipped(opening):
        # threshing floor in the dark: stacked sacks and a heap of grain, lit faintly from the door
        for cx, base, w, h, c in ((DX0 + 44, 842, 76, 110, ("#9a8a66", "#3a3020")),
                                  (DX0 + 108, 848, 80, 118, ("#8e7e5c", "#342a1c")),
                                  (DX0 + 170, 840, 74, 104, ("#807050", "#30281a")),
                                  (DX0 + 72, 758, 70, 96, ("#766850", "#2e2618")),
                                  (DX0 + 138, 764, 70, 98, ("#6e6048", "#2a2216"))):
            grain_sack(ic, cx, base, w, h, col=c)
        ic.fill(ic.poly_mask([(DX0, PBASE), (DX0 + 10, 862), (DX0 + 90, 846), (DX0 + 150, 858), (DX1, 866),
                              (DX1, PBASE)]), "#9a8048", "#4a3a1c", (846, PBASE), noise=0.3)
        ic.shade(opening, (14, 8, 4), 0.5)
        tint(ic, ic.mask("rectangle", (DX0, DTOP, DX1, DTOP + 130)), None, (0, 0, 0), 0.7, 24)
        tint(ic, ic.mask("rectangle", (DX1 - 40, DTOP, DX1, PBASE)), None, (0, 0, 0), 0.35, 16)
    # timber door frame
    ic.beam((DX0 - 14, DTOP - 8), (DX1 + 14, DTOP - 8), 24, (104, 72, 46))
    for x in (DX0 - 4, DX1 + 4):
        ic.beam((x, DTOP), (x, PBASE), 18, (98, 68, 44))
    # great door leaves swung open towards us, foreshortened
    left = [(DX0 - 14, DTOP + 2), (DX0 - 92, DTOP + 22), (DX0 - 92, PBASE + 16), (DX0 - 14, PBASE)]
    right = [(DX1 + 14, DTOP + 2), (DX1 + 92, DTOP + 22), (DX1 + 92, PBASE + 16), (DX1 + 14, PBASE)]
    lm = planks(ic, left, "#bc966a", "#76583a", board=18)
    rmask = planks(ic, right, "#a68258", "#5e4630", board=18)
    tint(ic, rmask, rmask, (0, 0, 0), 0.18)
    for leaf, m in ((left, lm), (right, rmask)):
        (ax, ay), (bx, by), (cx_, cy), (dx, dy) = leaf
        for f in (0.12, 0.88):
            ic.line([(ax, ay + (dy - ay) * f), (bx, by + (cy - by) * f)], 8, (70, 48, 30))
        ic.line([(ax, ay + (dy - ay) * 0.14), (bx, by + (cy - by) * 0.86)], 7, (76, 52, 32))  # brace
        for f in (0.2, 0.8):  # iron strap hinges
            ic.line([(ax, ay + (dy - ay) * f), (ax + (bx - ax) * 0.6, ay + (dy - ay) * f + (by - ay) * 0.6)], 5, IRON)
        ic.outline(leaf, 4, (40, 26, 16, 190))
    tint(ic, ic.mask("rectangle", (DX1 + 92, DTOP + 24, DX1 + 124, PBASE)), None, (0, 0, 0), 0.3, 10)
    ic.outline([(PX0, PEAVE), (PX0, PBASE), (PX1, PBASE), (PX1, PEAVE)], 5)
    # porch roof: both slopes, tiles, the right in shade
    lslope = [(PCX, PAPEX - 12), (PX0 - 40, PEAVE - 4), (PX0 - 16, PEAVE + 28), (PCX, PAPEX + 36)]
    rslope = [(PCX, PAPEX - 12), (PX1 + 40, PEAVE - 4), (PX1 + 16, PEAVE + 28), (PCX, PAPEX + 36)]
    shingles(ic, lslope, "#b06e52", "#5e3624", course=20, stagger=26, edge=6)
    rs = shingles(ic, rslope, "#8e5640", "#4a2a1c", course=20, stagger=26, edge=6)
    tint(ic, rs, rs, (0, 0, 0), 0.15)
    shadow = ic.poly_mask([(PX0 + 6, PEAVE + 4), (PCX, PAPEX + 34), (PX1 - 6, PEAVE + 4), (PX1 - 6, PEAVE + 40),
                           (PCX, PAPEX + 76), (PX0 + 6, PEAVE + 40)])
    tint(ic, shadow, gm, (0, 0, 0), 0.4, 10)
    ic.beam((PCX - 3, PAPEX - 34), (PCX + 3, PAPEX - 4), 12, (96, 66, 42))  # finial


def plinth(ic: Icon) -> None:
    stones(ic, (L - 8, BASE - 14, R + 8, BASE + 12), "#8e8270", "#5e5448", course=26, moss=0.0)
    ic.outline([(L - 8, BASE - 14), (R + 8, BASE - 14), (R + 8, BASE + 12), (L - 8, BASE + 12)], 4)


def sacks_left(ic: Icon) -> None:
    """A few grain sacks waiting beside the porch, one rolled open to show the grain."""
    tint(ic, ic.mask("ellipse", (20, 880, 180, 930)), None, (0, 0, 0), 0.35, 10)
    grain_sack(ic, 66, 922, 104, 148, col=("#d6c090", "#6a5434"))
    grain_sack(ic, 140, 934, 94, 116, open_top=True, col=("#ccb486", "#624e30"))


def wagon(ic: Icon) -> None:
    """Open four-wheeled farm wagon in profile heading right: boarded bed with stakes, piled with
    grain sacks and a cask, lashed with rope, the pole reaching down to the road."""
    x0, x1 = 596, 986
    bt, bb = 752, 826
    rw, fw = (684, 862, 88), (924, 874, 76)
    # far wheels in shadow
    wheel(ic, rw[0] - 24, rw[1] - 18, rw[2] * 0.96, tone=0.5)
    wheel(ic, fw[0] - 24, fw[1] - 18, fw[2] * 0.96, tone=0.5)
    # undercarriage: perch pole and bolsters
    ic.rect((x0 + 40, bb - 4, x1 - 30, bb + 22), "#4a3424", "#2a1c12", edge=4)
    # load, back to front
    cask(ic, x0 + 10, 604, x0 + 104, 784, wood=("#b0845a", "#4a2f1e"))
    for cx, base, w, h, c in ((740, 770, 104, 156, ("#dcc89a", "#6a5636")), (836, 774, 106, 150, ("#d2bc8e", "#62502f")),
                              (930, 776, 98, 140, ("#dec9a0", "#6c5838"))):
        grain_sack(ic, cx, base, w, h, col=c)
    sack(ic, 792, 642, 126, 88, c=("#e2d0a6", "#76623e"), lean=0.2)
    sack(ic, 894, 652, 118, 80, c=("#d6c196", "#6a5634"))
    # lashing over the load
    rope(ic, [(x0 + 70, bt - 6), (740, 664), (840, 620), (940, 652), (x1 - 10, bt - 6)], 5)
    # bed side boards, stakes
    bed = [(x0, bt), (x1, bt), (x1 - 8, bb), (x0 + 10, bb)]
    bm = hboards(ic, bed, "#9a744c", "#553a24", board=22)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, bt, x1, bb)), bm, (0, 0, 0), 0.22, 30)
    tint(ic, ic.mask("rectangle", (x0, bt, x1, bt + 16)), bm, (0, 0, 0), 0.25, 6)
    for x in (x0 + 14, 788, 884, x1 - 14):
        timber(ic, (x, bt - 34), (x - 3, bb + 2), 14, "#86603e", "#4a3220")
    ic.outline(bed, 5)
    # near wheels and the pole
    wheel(ic, *rw)
    wheel(ic, *fw)
    timber(ic, (x1 - 24, bb + 8), (1018, 936), 18, "#8a6444", "#4e3522")
    ic.line([(1008, 924), (1018, 940)], 8, IRON)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    wm = barn_walls(ic)
    rm = barn_roof(ic)
    louvre(ic, rm)
    tint(ic, ic.mask("rectangle", (L, EAVE, R, EAVE + 60)), wm, (0, 0, 0), 0.5, 12)  # eave shadow
    for x in (L + 14, 536, R - 14):
        buttress(ic, x)
    plinth(ic)
    porch(ic)
    sacks_left(ic)
    wagon(ic)
