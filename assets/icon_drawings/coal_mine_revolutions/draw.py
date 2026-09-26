"""Deep Colliery (coal_mine_revolutions): a stone engine house with its chimney winding over a heavy
twin-wheeled headgear, with a grey spoil tip and a black coal heap.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/coal_mine_revolutions/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/coal_mine_revolutions

Identity: the gabled stone engine house (slate roof, tall arched window) with a smoking brick stack,
ropes running from its gable over the twin wheels of a broad, braced and iron-strapped headgear,
a cage of coal at the landing stage, a grey shale spoil tip behind with a tub at its head, tubs on
the rails and the black coal heap bottom right. Tier 2 of the coal chain: stone and steam replace
the Colliery's boarded winding house, the single wheel doubles, the spoil tip appears.
Helpers are the coal family set (see coal_mine) plus ``sheave``, ``rope``, and ``stones``,
``bricks``, ``smoke`` (from victualling_yard and cookshop).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 13
REFS = ("schwaz_mine", "iron_foundry", "stone_quarry", "local_smelters")

COAL = ("#50505a", "#0a0a0e")  # lump lit / dark
COAL_BODY = ("#2e2e34", "#0c0c0e")
COAL_GLINT = (205, 214, 232)
IRON = (44, 42, 42)
GROUND = 905


# ---------------------------------------------------------------- helpers (coal family finish)
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
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 24, stagger: float = 30, edge: int = 6,
             var: float = 1.0) -> Image.Image:
    """Roof plane of short staggered shingles: every tile its own tone and ragged lower edge, a dark
    gap beside it and a soft shadow under it, and a drip edge of tile ends along the eaves."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys, xs = [p[1] for p in pts], [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.18, chroma=0.06)
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys) - course * 0.4, 0
    while y < max(ys) + course:
        x = min(xs) - stagger * (0.5 + 0.5 * (k % 2)) - rnd(0, 8)
        while x < max(xs) + stagger:
            w = stagger * rnd(0.7, 1.2)
            b0, b1 = y + course + rnd(-3, 4), y + course + rnd(-3, 4)
            q = [(x + 2, y), (x + w - 2, y), (x + w - 2, b1), (x + 2, b0)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(24, 12, 6, int(-t * 80 * var)) if t < 0 else (255, 238, 212, int(t * 60 * var)))
            td.line([(x + 3, b0 - 3), (x + w - 3, b1 - 3)], fill=(255, 236, 206, 70), width=3)  # lit butt
            td.line([(x + w - 1, y + 2), (x + w - 1, max(b0, b1))], fill=(34, 18, 10, 150), width=3)  # gap
            sd.line([(x + 2, b0 + 3), (x + w - 2, b1 + 3)], fill=255, width=6)
            x += w
        y += course
        k += 1
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.45, 2)
    # drip edge: the lowest course sticks out as a row of tile ends with a dark shadow line under it
    bl, br = max(pts, key=lambda p: (p[1], -p[0])), max(pts, key=lambda p: (p[1], p[0]))
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    drip = tuple((a + b) // 2 for a, b in zip(ImageColor.getrgb(c1), ImageColor.getrgb(c2)))
    x = min(bl[0], br[0]) - 4
    while x < max(bl[0], br[0]) + 4:
        w = stagger * rnd(0.6, 1.0)
        d.polygon([(x + 1, bl[1] - 6), (x + w - 1, bl[1] - 6), (x + w - 2, bl[1] + rnd(4, 10)), (x + 2, bl[1] + rnd(4, 10))],
                  fill=drip + (255,))
        d.line([(x + 3, bl[1] - 4), (x + w - 3, bl[1] - 4)], fill=(230, 196, 150, 150), width=3)
        d.line([(x + w - 1, bl[1] - 5), (x + w - 1, bl[1] + 6)], fill=(30, 16, 8, 200), width=3)
        x += w
    ic.image.alpha_composite(lay)
    if edge:
        ic.outline(pts, edge)
    ic.line([(bl[0] - 2, bl[1] + 10), (br[0] + 2, br[1] + 10)], 4, (30, 18, 10, 190))
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#9a6638", c2="#50301a") -> None:
    """Squared beam: lit upper half, darker lower half, a grain highlight, thin dark rim."""
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


def planks(ic: Icon, pts, c1="#946236", c2="#50301a", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, grain strokes, soft joints; returns the mask."""
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


def coal_lump(ic: Icon, cx: float, cy: float, r: float, tone: float = 1.0, glint: bool = False) -> None:
    """One angular lump of coal: few sharp facets fanned from an off-centre apex, the facets facing
    the upper-left light cool grey, the others near black; a glint only when asked."""
    R = ic.random
    n = R.randint(4, 6)
    rot = R.uniform(0, 2 * math.pi)
    flat = R.uniform(0.6, 0.85)
    angs = sorted(rot + 2 * math.pi * (i + R.uniform(-0.25, 0.25)) / n for i in range(n))
    pts = [(cx + math.cos(a) * r * R.uniform(0.82, 1.18), cy + math.sin(a) * r * flat * R.uniform(0.82, 1.18))
           for a in angs]
    k = lambda c: tuple(min(255, int(v * tone)) for v in c)  # noqa: E731
    m = ic.poly_mask(pts)
    ic.fill(m, k((66, 66, 76)), k((12, 12, 16)), radial=(cx - r * 0.8, cy - r * 0.8, r * 2.6), noise=0.22, chroma=0.04)
    ax, ay = cx - r * R.uniform(0.0, 0.3), cy - r * flat * R.uniform(0.1, 0.4)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        mx, my = (x0 + x1) / 2 - ax, (y0 + y1) / 2 - ay
        f = (-mx * 0.6 - my * 0.8) / (math.hypot(mx, my) or 1)
        if f > 0.25:
            fill = (150, 158, 178, int((30 + 70 * f) * R.uniform(0.6, 1.0) * tone))
        elif f < -0.2:
            fill = (0, 0, 0, int(70 + 100 * -f))
        else:
            fill = (110, 114, 128, int(R.uniform(0, 45)))
        d.polygon([(ax, ay), (x0, y0), (x1, y1)], fill=fill)
    for p in R.sample(pts, 2):  # crisp ridges between facets
        d.line([(ax, ay), p], fill=(150, 156, 172, 45), width=2)
    paste_clipped(ic, lay, m)
    if glint:
        e = min(range(n), key=lambda i: pts[i][0] + pts[i][1])
        p0, p1 = pts[e], pts[(e + 1) % n]
        ic.line([p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)], 3, (228, 236, 248, 200))
    ic.outline(pts, 3, (6, 6, 8, 220))


def lump_size(ic: Icon, big: float = 0.14) -> float:
    """Size factor: a few large slabs, some mid lumps, many small ones."""
    u = ic.random.random()
    if u < big:
        return ic.random.uniform(1.1, 1.4)
    if u < big + 0.34:
        return ic.random.uniform(0.7, 1.0)
    return ic.random.uniform(0.32, 0.55)


def coal_heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float, rows: int) -> Image.Image:
    """Mound of coal: a black gritty body, then lumps of very different sizes laid back to front
    (large slabs mostly low, where they roll); returns the body mask."""
    R = ic.random
    cx = (x0 + x1) / 2
    outline = [(x0, base), (x0 + (cx - x0) * 0.4, base - (base - top) * 0.6), (cx - r * 0.8, top + r * 0.3),
               (cx + r * 0.6, top + r * 0.2), (x1 - (x1 - cx) * 0.35, base - (base - top) * 0.55), (x1, base)]
    ic.poly(outline, COAL_BODY[0], COAL_BODY[1], noise=0.3)
    body = ic.poly_mask(outline)
    lumps = []
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.45 + (base - top - r * 0.8) * t
        half = (x1 - x0) / 2 * (0.2 + 0.74 * t)
        x = cx - half + R.uniform(0, r * 0.3)
        while x < cx + half:
            rr = r * lump_size(ic, 0.05 + 0.18 * t)
            lumps.append((x + rr * 0.5, y + R.uniform(-r * 0.3, r * 0.3), rr))
            x += rr * R.uniform(0.75, 1.05)
    lumps.sort(key=lambda p: p[1] + p[2] * 0.5)
    for x, y, rr in lumps:
        coal_lump(ic, x, y, rr, R.uniform(0.8, 1.15), glint=R.random() < 0.12)
    tint(ic, ic.mask("rectangle", (cx, top, x1 + 20, base + 10)), body, (0, 0, 0), 0.25, 30)  # shadow side
    return body


def tub(ic: Icon, x0: float, x1: float, top: float, bottom: float, load: bool = True) -> None:
    """Wooden coal tub on small iron wheels, heaped with mixed lumps, lit from the upper left."""
    w = x1 - x0
    if load:
        R = ic.random
        lumps = [(0.5, -0.1, 0.2), (0.22, -0.04, 0.13), (0.8, -0.03, 0.12)]
        for _ in range(9):
            lumps.append((R.uniform(0.05, 0.95), R.uniform(-0.12, 0.02), R.uniform(0.05, 0.09)))
        for fx, fy, fr in sorted(lumps, key=lambda p: p[1]):
            coal_lump(ic, x0 + w * fx, top + w * fy, w * fr, R.uniform(0.85, 1.12), glint=R.random() < 0.15)
    body = [(x0 - 8, top), (x1 + 8, top), (x1 - 6, bottom), (x0 + 6, bottom)]
    bm = planks(ic, body, "#9a6a3e", "#4a2c16", board=w / 5)
    ic.overlay(lambda d: d.line([(x0 - 4, (top + bottom) / 2), (x1 + 4, (top + bottom) / 2)], fill=(40, 24, 12, 90),
                                width=3), bm)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top, x1 + 20, bottom)), bm, (0, 0, 0), 0.3, 16)
    for x in (x0 - 2, x1 + 2):  # iron corner straps
        ic.line([(x, top + 2), (x + (4 if x < x1 else -4), bottom - 2)], 9, IRON)
    ic.line([(x0 - 8, top + 4), (x1 + 8, top + 4)], 9, (58, 54, 52))
    ic.line([(x0 - 6, top + 1), (x1 + 6, top + 1)], 2, (180, 170, 160, 120))
    ic.outline(body, 4, (40, 26, 16, 170))
    wr = (bottom - top) * 0.3
    for wx in (x0 + w * 0.2, x1 - w * 0.2):
        ic.ellipse((wx - wr, bottom - wr * 0.4, wx + wr, bottom + wr * 1.6), "#5a5654", "#242222", edge=4)
        ic.draw.ellipse((wx - 6, bottom + wr * 0.6 - 6, wx + 6, bottom + wr * 0.6 + 6), fill=(30, 28, 26, 255))


def rails(ic: Icon, x0: float, x1: float, y: float, gauge: float = 18) -> None:
    """Plank sleepers and a pair of timber rails seen from the raised camera."""
    x = x0
    while x < x1:
        ic.rect((x, y - 6, x + 16, y + gauge + 10), "#7a5232", "#40291a", edge=3)
        x += ic.random.uniform(40, 52)
    for yy in (y, y + gauge):
        ic.line([(x0 - 6, yy), (x1 + 6, yy)], 9, (48, 34, 22))
        ic.line([(x0 - 6, yy - 2), (x1 + 6, yy - 2)], 3, (170, 140, 104, 160))


def rope(ic: Icon, pts, width: int = 6) -> None:
    """Hemp rope: warm light brown core, a thin darker rim and a highlight along its upper edge."""
    ic.line(pts, width + 4, (74, 52, 30, 200))
    ic.line(pts, width, (188, 154, 106))
    ic.line([(x - 1, y - max(1, width // 3)) for x, y in pts], max(2, width // 3), (240, 220, 178, 170))


def sheave(ic: Icon, cx: float, cy: float, r: float, spokes: int = 8, rim=("#94694a", "#4a2c16"),
           iron: bool = False) -> None:
    """Winding wheel facing the viewer: thick rim with a groove, spokes, hub; lit upper left."""
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8)))
    spoke_col = (72, 70, 70) if iron else (110, 78, 50)
    for a in np.linspace(0, math.pi, spokes // 2, endpoint=False) + 0.2:
        p0 = (cx + math.cos(a) * r * 0.84, cy + math.sin(a) * r * 0.84)
        p1 = (cx - math.cos(a) * r * 0.84, cy - math.sin(a) * r * 0.84)
        ic.line([p0, p1], int(r * 0.13) + 5, (36, 24, 16, 230))
        ic.line([p0, p1], int(r * 0.13), spoke_col)
    ic.fill(ring, rim[0], rim[1], radial=(cx - r * 0.7, cy - r * 0.7, r * 2.2), noise=0.18)
    ic.overlay(lambda d: d.ellipse((cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9), outline=(30, 22, 16, 200),
                                   width=5))
    ic.overlay(lambda d: d.arc((cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5), 190, 280, fill=(255, 236, 200, 110),
                               width=5))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 26, 16, 200), width=5))
    hr = r * 0.2
    ic.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), "#6a6664", "#2a2826", edge=4)


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
            col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        y += course
        k += 1
    paste_clipped(ic, lay, m)


def smoke(ic: Icon, puffs) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, "#dedad2", "#7e7a76", radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


# ---------------------------------------------------------------- parts
HX0, HX1, EAVE, PEAK = 112, 412, 486, 330  # engine house
HCX = (HX0 + HX1) / 2
GL, GR = 436, 872  # headgear leg feet
TOPY = 320
LX, RX = 548, 764  # leg heads
WHEELS = ((712, 250, 82), (590, 256, 82))  # back wheel first
HOLE = (356, 520)  # rope opening in the engine house gable


def chimney(ic: Icon) -> None:
    """Tall tapering brick stack beside the engine house, stone base, lit on the left."""
    pts = [(40, GROUND), (62, 190), (116, 190), (136, GROUND)]
    m = ic.poly_mask(pts)
    bricks(ic, m, (30, 190, 140, GROUND), "#a0664a", "#5a3626", course=16, length=34)
    tint(ic, ic.mask("rectangle", (96, 170, 160, GROUND)), m, (0, 0, 0), 0.35, 14)
    tint(ic, ic.mask("rectangle", (30, 170, 140, 330)), m, (14, 10, 8), 0.4, 30)  # soot at the top
    ic.outline(pts, 5)
    ic.rect((54, 174, 124, 198), "#8a5a44", "#4a2e22", edge=4)  # oversailing cap
    ic.fill(ic.mask("ellipse", (62, 166, 116, 184)), "#1c1612", "#0a0806", noise=0.05)


def engine_house(ic: Icon) -> None:
    """Stone engine house, gable to the viewer: slate roof receding behind, tall arched window,
    the rope opening high on the right, dressed quoins and a sooty top."""
    dx, dy = 40, -30  # roof depth seen from the raised camera
    ridge = [(HX0 - 18, EAVE + 10), (HCX, PEAK - 12), (HX1 + 18, EAVE + 10)]
    roof = ridge + [(x + dx, y + dy) for x, y in ridge[::-1]]
    shingles(ic, roof, "#7c8088", "#3e424a", course=20, stagger=28, edge=6, var=0.45)
    gable = [(HX0, GROUND), (HX0, EAVE), (HCX, PEAK), (HX1, EAVE), (HX1, GROUND)]
    gm = ic.poly_mask(gable)
    stones(ic, (HX0, PEAK, HX1, GROUND), "#ccb492", "#86725a", course=34, clip=gm, moss=0.05)
    tint(ic, ic.mask("rectangle", (HCX + 40, PEAK, HX1 + 40, GROUND)), gm, (0, 0, 0), 0.22, 40)
    tint(ic, ic.mask("rectangle", (HX0, GROUND - 90, HX1, GROUND)), gm, (40, 40, 22), 0.3, 24)
    tint(ic, ic.poly_mask([(HX0, EAVE), (HCX, PEAK), (HX1, EAVE), (HX1, EAVE + 60), (HX0, EAVE + 60)]), gm,
         (20, 16, 14), 0.2, 30)
    # verge boards along the gable
    for p0, p1 in (((HX0 - 20, EAVE + 12), (HCX, PEAK - 8)), ((HCX, PEAK - 8), (HX1 + 20, EAVE + 12))):
        ic.line([p0, p1], 20, (60, 62, 68))
        ic.line([(p0[0], p0[1] - 5), (p1[0], p1[1] - 5)], 4, (170, 176, 184, 150))
    # dressed quoins
    for x0, x1 in ((HX0, HX0 + 30), (HX1 - 30, HX1)):
        y, k = EAVE + 6, 0
        while y < GROUND - 30:
            w = (30 if k % 2 else 20)
            h = ic.random.uniform(26, 32)
            bx = (x0, y, x0 + w, y + h) if x0 == HX0 else (x1 - w, y, x1, y + h)
            ic.rect(bx, "#dcc8a6", "#9c8668", edge=0)
            ic.line([(bx[0], bx[3]), (bx[2], bx[3])], 4, (40, 28, 20, 140))
            y += h + 2
            k += 1
    # tall round-arched window and a smaller one, dark
    for x0, x1, y0, y1 in ((HCX - 42, HCX + 42, 480, 720), (HCX - 26, HCX + 26, 380, 440)):
        w = x1 - x0
        arch = union(ic.mask("ellipse", (x0 - 14, y0 - 14, x1 + 14, y0 + w + 14)),
                     ic.mask("rectangle", (x0 - 14, y0 + w / 2, x1 + 14, y1 + 12)))
        ic.fill(arch, "#dccaa8", "#a08a6a", (y0, y1), noise=0.12)
        op = union(ic.mask("ellipse", (x0, y0, x1, y0 + w)), ic.mask("rectangle", (x0, y0 + w / 2, x1, y1)))
        ic.fill(op, "#34302e", "#161414", (y0, y1), noise=0.08)
        ic.shade(ic.intersect(ic.poly_mask([(x0, y0), (x0 + w * 0.6, y0), (x0, y0 + w)]), op), (150, 160, 175), 0.14)
        ic.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], 6, (84, 70, 56))
        for f in (0.45, 0.72):
            ic.line([(x0, y0 + (y1 - y0) * f), (x1, y0 + (y1 - y0) * f)], 6, (84, 70, 56))
    # arched door, bottom left
    ic.door(150, 800, 222, GROUND, arched=True, surround="#c8bca6")
    # rope opening high on the right
    hx, hy = HOLE
    ic.ellipse((hx - 26, hy - 26, hx + 26, hy + 26), "#d8c6a4", "#968064", edge=4)
    ic.ellipse((hx - 16, hy - 16, hx + 16, hy + 16), "#161210", "#060404", edge=0)
    ic.outline(gable, 6)


def spoil_tip(ic: Icon) -> None:
    """Low, broad tip of dark shale behind the headgear, scree streaks and a faint incline rail."""
    pts = [(540, GROUND), (610, 790), (700, 700), (790, 640), (870, 612), (930, 616), (980, 648), (1012, 710),
           (1018, 800), (1018, GROUND)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#7e7062", "#3a322c", radial=(800, 560, 480), noise=0.3, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(40):
        x, y = ic.random.uniform(600, 1018), ic.random.uniform(600, 880)
        L = ic.random.uniform(20, 50)
        dxl = 0.5 if x > 900 else -0.5
        d.line([(x, y), (x + L * dxl, y + L * 0.7)],
               fill=(30, 26, 22, 80) if ic.random.random() < 0.6 else (190, 180, 164, 50), width=4)
    paste_clipped(ic, lay, m)
    tint(ic, ic.mask("rectangle", (920, 560, 1060, GROUND)), m, (0, 0, 0), 0.3, 30)
    for off in (0, 20):  # faint incline rail up the tip
        ic.line([(660 + off, 800), (880 + off, 598)], 5, (40, 32, 24, 150))
    for t in np.linspace(0.08, 0.92, 7):
        x, y = 660 + 220 * t, 800 - 202 * t
        ic.line([(x - 4, y + 4), (x + 26, y - 4)], 4, (70, 56, 40, 130))
    ic.outline(pts, 6)


def plate(ic: Icon, x: float, y: float, w: float, h: float) -> None:
    """Riveted iron plate: dark body, a lit top edge, a row of rivet heads."""
    ic.rect((x - w / 2, y - h / 2, x + w / 2, y + h / 2), "#54545a", "#1e1e22", edge=4)
    ic.line([(x - w / 2 + 3, y - h / 2 + 3), (x + w / 2 - 3, y - h / 2 + 3)], 3, (190, 194, 204, 150))
    for rx in np.linspace(x - w / 2 + 8, x + w / 2 - 8, max(2, int(w // 18))):
        ic.draw.ellipse((rx - 3, y - 3, rx + 3, y + 3), fill=(150, 152, 160, 255))


def headgear(ic: Icon) -> None:
    """Heavy braced timber headgear bound in iron: riveted plates on every joint, iron shoes, a heavy
    iron-capped cross-head with bearing blocks under the twin wheels."""
    timber(ic, (LX + 10, TOPY + 10), (300, 700), 30, "#8a5a32", "#4a2c16")
    timber(ic, (LX + 40, TOPY + 30), (340, 760), 22, "#6e4a2a", "#3a2412")
    for (xa, ya), (xb, yb) in (((GL + 70, GROUND - 40), (LX + 18, TOPY + 24)),
                               ((GR - 70, GROUND - 40), (RX - 18, TOPY + 24))):
        timber(ic, (xa, ya), (xb, yb), 24, "#5e3c24", "#34221a")

    def at(y: float, left: bool) -> float:
        t = (GROUND - y) / (GROUND - TOPY)
        return GL + (LX - GL) * t if left else GR + (RX - GR) * t

    ys = (TOPY + 24, 470, 620, 760, GROUND - 50)
    for ya, yb in zip(ys, ys[1:]):
        timber(ic, (at(ya, True), ya), (at(yb, False), yb), 18, "#96643a", "#4e2e18")
        timber(ic, (at(ya, False), ya), (at(yb, True), yb), 18, "#96643a", "#4e2e18")
    for y in ys[1:]:
        timber(ic, (at(y, True) - 16, y), (at(y, False) + 16, y), 26, "#a86a38", "#583418")
    for left in (True, False):
        x0 = GL if left else GR
        x1 = LX if left else RX
        timber(ic, (x0, GROUND + 6), (x1, TOPY), 42, "#b8743e", "#603a1e")
        # iron strap running up the outer face of the leg
        t0, t1 = (x0 + (8 if left else -8), GROUND - 10), (x1 + (6 if left else -6), TOPY + 30)
        ic.line([t0, t1], 9, (40, 40, 44))
        ic.line([(t0[0] - 3, t0[1]), (t1[0] - 3, t1[1])], 2, (170, 172, 182, 120))
        for y in ys[1:]:
            plate(ic, at(y, left), y, 62, 34)
        ic.rect((x0 - 30, GROUND - 26, x0 + 30, GROUND + 10), "#5a5a60", "#222226", edge=4)  # iron shoe
    # heavy cross-head: timber sill capped by an iron girder, bearing blocks under the wheels
    timber(ic, (LX - 80, TOPY + 4), (RX + 80, TOPY + 4), 48, "#b87a44", "#5e381a")
    ic.rect((LX - 88, TOPY - 34, RX + 88, TOPY - 14), "#606066", "#26262a", edge=5)
    ic.line([(LX - 84, TOPY - 31), (RX + 84, TOPY - 31)], 3, (196, 200, 210, 160))
    for x in (LX - 50, RX + 50):
        plate(ic, x, TOPY + 4, 44, 40)
    tint(ic, ic.mask("rectangle", (LX - 70, TOPY + 28, RX + 70, TOPY + 64)), None, (0, 0, 0), 0.35, 8)


def heapstead(ic: Icon) -> None:
    """Boarded pit-head house round the foot of the headgear: shingled roof, a dark banking door
    where the tubs run out onto the rails."""
    x0, x1, eave, ridge = 452, 884, 790, 706
    ic.fill(ic.mask("rectangle", (x0 + 10, eave - 20, x1 - 10, eave + 24)), "#3e3026", "#231a14", noise=0.1)
    roof = [(x0 - 22, eave + 10), (x1 + 22, eave + 10), (x1 - 12, ridge), (x0 + 16, ridge)]
    rm = planks(ic, roof, "#8e6a4a", "#56392a", board=24)  # boarded roof, boards running down the slope
    tint(ic, ic.mask("rectangle", (760, ridge - 10, x1 + 40, eave + 20)), rm, (0, 0, 0), 0.2, 30)
    tint(ic, ic.mask("rectangle", (x0 - 30, eave - 16, x1 + 30, eave + 12)), rm, (0, 0, 0), 0.3, 6)
    ic.outline(roof, 6)
    ic.line([(x0 + 18, ridge + 4), (x1 - 14, ridge + 4)], 10, (70, 48, 32))
    ic.line([(x0 + 18, ridge + 1), (x1 - 14, ridge + 1)], 4, (240, 214, 176, 120))
    wall = [(x0, eave + 10), (x1, eave + 10), (x1, GROUND), (x0, GROUND)]
    wm = planks(ic, wall, "#a47444", "#5a3a1e", board=28)
    tint(ic, ic.mask("rectangle", (x0, eave + 10, x1, eave + 60)), wm, (0, 0, 0), 0.5, 12)
    tint(ic, ic.mask("rectangle", (x0, GROUND - 60, x1, GROUND)), wm, (30, 34, 18), 0.25, 18)
    dx0, dx1 = 590, 720
    door = ic.mask("rectangle", (dx0, 830, dx1, GROUND))
    ic.fill(door, "#261c14", "#0e0a07", (830, GROUND), noise=0.1)
    tint(ic, ic.mask("rectangle", (dx0, 830, dx1, 862)), door, (0, 0, 0), 0.5, 8)
    timber(ic, (dx0 - 12, 826), (dx1 + 12, 826), 18, "#8a5a32", "#4a2c16")
    for x in (dx0 - 4, dx1 + 4):
        timber(ic, (x, 830), (x, GROUND), 16, "#8a5a32", "#4a2c16")
    ic.outline(wall, 5)


def cage(ic: Icon, cx: float, top: float) -> None:
    """Iron-framed cage on the rope, a tub of coal inside."""
    w, h = 120, 118
    tub(ic, cx - 44, cx + 44, top + 60, top + h - 18)
    for x in (cx - w / 2, cx + w / 2):
        ic.line([(x, top), (x, top + h)], 10, (48, 46, 46))
    for y in (top, top + h):
        ic.line([(cx - w / 2 - 4, y), (cx + w / 2 + 4, y)], 12, (52, 50, 50))
    ic.line([(cx - w / 2, top + 4), (cx + w / 2, top + 4)], 3, (170, 166, 160, 130))
    for x in (cx - w / 2 + 8, cx + w / 2 - 8):
        ic.line([(x, top), (cx, top - 60)], 6, (52, 50, 50))


def apron(ic: Icon) -> None:
    pts = [(14, 962), (30, GROUND - 8), (1010, GROUND - 8), (1016, 962)]
    ic.poly(pts, "#746452", "#463a2e", noise=0.32)
    tint(ic, ic.poly_mask([(430, GROUND), (1010, GROUND), (1016, 960), (420, 960)]), None, (18, 16, 16), 0.4, 18)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.62
    ic.grade["mute"] = 0.98
    smoke(ic, [(246, 124, 36), (188, 138, 42), (130, 160, 34)])
    spoil_tip(ic)
    apron(ic)
    chimney(ic)
    headgear(ic)
    heapstead(ic)
    engine_house(ic)
    hx, hy = HOLE
    (bx, by, br), (fx, fy, fr) = WHEELS
    rope(ic, [(hx, hy), (bx - br * 0.2, by - br + 4)])
    rope(ic, [(hx, hy), (fx - fr + 6, fy - 16)])
    sheave(ic, bx, by, br, rim=("#6a6a72", "#26262c"), iron=True)
    sheave(ic, fx, fy, fr, rim=("#8e9098", "#34343a"), iron=True)
    rope(ic, [(fx + fr - 8, fy + 10), (fx + fr - 8, 520)])
    rope(ic, [(bx + br - 8, by + 10), (bx + br - 8, 690)])
    cage(ic, fx + fr - 8, 580)
    rails(ic, 30, 700, 926)
    tub(ic, 460, 624, 816, 900)
    coal_heap(ic, 704, 1018, 984, 716, 38, 8)
