"""Colliery (coal_mine_improved): a timber headframe with its winding wheel over a shaft, a boarded
winding house and a black coal heap.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/coal_mine_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/coal_mine_improved

Identity: the tall splayed timber headframe crowned by a spoked winding wheel, the rope running from
the drum in the winding house over the wheel and down the shaft to a kibble of coal; the shaft
collar sits on a timber curb. A boarded, shingled winding house stands on the left, a coal tub on
its rails before it, and the black coal heap bottom right, as in the Coal Drift. Tier 1 of the coal
chain: the drift's hillside gives way to a sunk shaft and winding gear; the Deep Colliery adds a
stone engine house, chimney and a larger headgear. Helpers are the coal family set (see coal_mine)
plus ``sheave`` and ``rope``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 12
REFS = ("schwaz_mine", "clay_pit", "stone_quarry", "sand_pit")

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


GL, GR = 448, 812  # headframe leg feet
TOPY = 262  # headframe cap
SX, SY, SR = 630, 206, 92  # sheave


HX0, HX1, EAVE, PEAK = 40, 404, 610, 372  # winding house, gable to the viewer
HCX = (HX0 + HX1) / 2


def winding_house(ic: Icon) -> None:
    """Boarded winding house, gable to the viewer under a steep shingled roof, a stone stove chimney
    with a wisp of smoke, and a dark recessed opening where the rope drum turns in shadow."""
    dx, dy = 44, -30  # roof depth seen from the raised camera
    ridge = [(HX0 - 22, EAVE + 12), (HCX, PEAK - 14), (HX1 + 22, EAVE + 12)]
    roof = ridge + [(x + dx, y + dy) for x, y in ridge[::-1]]
    rm = shingles(ic, roof, "#a87c58", "#5a3c26", course=22, stagger=28, edge=6)
    tint(ic, ic.mask("rectangle", (HCX, PEAK - 60, HX1 + 80, EAVE + 20)), rm, (0, 0, 0), 0.2, 30)
    # stone stove chimney through the left slope, a thin wisp of smoke drifting up-left
    cx0, cx1, ctop = 92, 146, 300
    smoke(ic, [(50, 160, 26), (70, 190, 30), (94, 224, 28), (114, 258, 22)])
    ch = [(cx0, 560), (cx0, ctop), (cx1, ctop), (cx1, 520)]
    cm = ic.poly_mask(ch)
    stones(ic, (cx0, ctop, cx1, 560), "#b4a48a", "#6e6250", course=24, clip=cm, moss=0.0)
    tint(ic, ic.mask("rectangle", (cx0 + 30, ctop, cx1 + 20, 560)), cm, (0, 0, 0), 0.3, 8)
    tint(ic, ic.mask("rectangle", (cx0, ctop, cx1, ctop + 40)), cm, (14, 10, 8), 0.4, 12)
    ic.outline(ch, 5)
    ic.rect((cx0 - 8, ctop - 14, cx1 + 8, ctop + 6), "#a09078", "#5e5446", edge=4)
    # gable wall of vertical boards
    gable = [(HX0, GROUND), (HX0, EAVE), (HCX, PEAK), (HX1, EAVE), (HX1, GROUND)]
    wm = planks(ic, gable, "#bc8448", "#5e381a", board=30)
    tint(ic, ic.poly_mask([(HX0, EAVE), (HCX, PEAK), (HX1, EAVE), (HX1, EAVE + 70), (HX0, EAVE + 70)]), wm,
         (0, 0, 0), 0.4, 18)  # under the verges
    tint(ic, ic.mask("rectangle", (HCX + 60, PEAK, HX1 + 40, GROUND)), wm, (0, 0, 0), 0.16, 40)
    tint(ic, ic.mask("rectangle", (HX0, GROUND - 80, HX1, GROUND)), wm, (30, 34, 18), 0.25, 20)
    tint(ic, ic.mask("rectangle", (292, 790, HX1, GROUND)), wm, (10, 6, 4), 0.42, 16)  # behind the tub
    for p0, p1 in (((HX0 - 24, EAVE + 14), (HCX, PEAK - 10)), ((HCX, PEAK - 10), (HX1 + 24, EAVE + 14))):
        ic.line([p0, p1], 18, (96, 62, 36))  # verge boards
        ic.line([(p0[0], p0[1] - 5), (p1[0], p1[1] - 5)], 4, (240, 204, 150, 150))
    timber(ic, (HX0 + 8, EAVE + 6), (HX0 + 8, GROUND), 22, "#a06a3a", "#4a2c16")
    timber(ic, (HX1 - 8, EAVE + 6), (HX1 - 8, GROUND), 22, "#a06a3a", "#4a2c16")
    # small loft hatch under the peak, dark
    ic.rect((HCX - 26, 470, HCX + 26, 530), "#241a12", "#0c0806", edge=4)
    timber(ic, (HCX - 34, 466), (HCX + 34, 466), 14, "#b07844", "#5a381c")
    # recessed drum opening: deep shadow, the drum only picked out by a dull rim light
    ox0, ox1, oy0, oy1 = 168, 376, 648, 842
    op = ic.mask("rectangle", (ox0, oy0, ox1, oy1))
    ic.fill(op, "#1c140e", "#080504", (oy0, oy1), noise=0.1)
    with ic.clipped(op):
        dx0, dx1, dy0, dy1 = 196, 350, 704, 800
        ic.fill(ic.mask("rectangle", (dx0, dy0, dx1, dy1)), "#5a3e26", "#1e140c", (dy0, dy1), noise=0.18)
        for y in np.arange(dy0 + 8, dy1, 11):
            ic.line([(dx0, y), (dx1, y + 3)], 4, (110, 88, 60, 150))
        for x in (dx0, dx1):
            ic.ellipse((x - 14, dy0 - 18, x + 14, dy1 + 18), "#4a3422", "#1a120c", edge=4)
        ic.line([(dx0 + 4, dy0 + 2), (dx1 - 4, dy0 + 2)], 3, (200, 160, 110, 120))
        tint(ic, ic.mask("rectangle", (ox0, oy0, ox1, oy0 + 50)), None, (0, 0, 0), 0.65, 14)  # lintel shadow
        tint(ic, ic.mask("rectangle", (ox0, oy0, ox0 + 40, oy1)), None, (0, 0, 0), 0.5, 12)  # reveal shadow
        tint(ic, ic.mask("rectangle", (ox1 - 18, oy0, ox1, oy1)), None, (120, 84, 50), 0.35, 4)  # lit reveal
    timber(ic, (ox0 - 14, oy0 - 8), (ox1 + 14, oy0 - 8), 22, "#c48a50", "#5a381c")
    timber(ic, (ox0 - 6, oy0), (ox0 - 6, oy1 + 4), 18, "#b07844", "#4a2c16")
    timber(ic, (ox1 + 6, oy0), (ox1 + 6, oy1 + 4), 18, "#b07844", "#4a2c16")
    ic.rect((ox0 - 16, oy1, ox1 + 16, oy1 + 18), "#a06a3a", "#4a2c16", edge=4)
    # small plank door on the left
    door = [(64, 730), (140, 730), (140, GROUND), (64, GROUND)]
    ic.fill(ic.poly_mask(door), "#2a1c12", "#140c08", (730, GROUND))
    planks(ic, [(68, 734), (136, 734), (136, GROUND), (68, GROUND)], "#8a5a32", "#40281a", board=20)
    ic.outline(door, 4, (40, 26, 16, 170))
    for y in (770, 856):
        ic.line([(70, y), (132, y)], 7, (48, 46, 46))
    ic.outline(gable, 5)


def headframe(ic: Icon) -> None:
    """Splayed four-post timber headframe: three bays, an X in the upper two, a single raker in the
    lowest, warm lit timber, and the wheel on top."""
    lx, rx = 574, 686  # leg heads
    for (xa, ya), (xb, yb) in (((GL + 60, GROUND - 40), (lx + 16, TOPY + 20)), ((GR - 60, GROUND - 40), (rx - 16, TOPY + 20))):
        timber(ic, (xa, ya), (xb, yb), 20, "#6a4628", "#3a281a")

    def at(y: float, left: bool) -> float:
        t = (GROUND - y) / (GROUND - TOPY)
        return GL + (lx - GL) * t if left else GR + (rx - GR) * t

    ys = (TOPY + 20, 480, 700, GROUND - 50)
    for i, (ya, yb) in enumerate(zip(ys, ys[1:])):
        timber(ic, (at(ya, True), ya), (at(yb, False), yb), 15, "#b07a48", "#5a3a1e")
        if i < 2:
            timber(ic, (at(ya, False), ya), (at(yb, True), yb), 15, "#b07a48", "#5a3a1e")
    for y in ys[1:]:
        timber(ic, (at(y, True) - 14, y), (at(y, False) + 14, y), 22, "#c08450", "#5e3a1c")
    timber(ic, (GL, GROUND + 6), (lx, TOPY), 32, "#d09258", "#66401e")
    timber(ic, (GR, GROUND + 6), (rx, TOPY), 32, "#c08450", "#5a381a")
    timber(ic, (lx - 40, TOPY), (rx + 40, TOPY), 34, "#d49a5c", "#6a3e1c")
    tint(ic, ic.mask("rectangle", (lx - 30, TOPY + 17, rx + 30, TOPY + 50)), None, (0, 0, 0), 0.35, 8)


def shaft(ic: Icon) -> None:
    """Shaft collar: dark mouth seen from above inside a timber curb."""
    x0, x1 = 530, 730
    mouth = ic.mask("ellipse", (x0 + 16, GROUND - 42, x1 - 16, GROUND + 6))
    ic.fill(mouth, "#1c1612", "#060404", (GROUND - 42, GROUND), noise=0.08)
    ic.rect((x0, GROUND - 14, x1, GROUND + 30), "#9a6a3c", "#4a2c16", edge=5)
    ic.line([(x0 + 4, GROUND - 10), (x1 - 4, GROUND - 10)], 3, (255, 228, 190, 90))
    for x in (x0 + 60, x0 + 130):
        ic.line([(x, GROUND - 12), (x, GROUND + 28)], 3, (40, 26, 16, 150))


def kibble(ic: Icon, cx: float, top: float) -> None:
    """Iron-hooped kibble of coal hanging on the rope."""
    w, h = 96, 84
    for dx, dy, r in ((-24, -4, 20), (6, -14, 24), (30, -2, 18), (-6, 4, 18)):
        coal_lump(ic, cx + dx, top + dy, r)
    body = [(cx - w / 2, top), (cx + w / 2, top), (cx + w * 0.4, top + h), (cx - w * 0.4, top + h)]
    planks(ic, body, "#9a6638", "#46301e", board=18)
    tint(ic, ic.mask("rectangle", (cx + 4, top, cx + w, top + h)), ic.poly_mask(body), (0, 0, 0), 0.3, 10)
    for f in (0.12, 0.85):
        y = top + h * f
        ic.line([(cx - w / 2 + 2 + 8 * f, y), (cx + w / 2 - 2 - 8 * f, y)], 9, (52, 50, 50))
    ic.outline(body, 4, (40, 26, 16, 170))
    rope(ic, [(cx - w / 2 + 6, top + 4), (cx, top - 60), (cx + w / 2 - 6, top + 4)], 4)


def apron(ic: Icon) -> None:
    pts = [(14, 962), (34, GROUND - 8), (1000, GROUND - 8), (1012, 962)]
    ic.poly(pts, "#7a6a56", "#4a3e32", noise=0.32)
    tint(ic, ic.poly_mask([(460, GROUND), (1000, GROUND), (1010, 960), (440, 960)]), None, (18, 16, 16), 0.4, 18)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.56
    ic.grade["mute"] = 0.97
    apron(ic)
    winding_house(ic)
    headframe(ic)
    sheave(ic, SX, SY, SR, rim=("#b08058", "#4e2e18"))
    # rope: drum -> over the wheel -> down the shaft
    rope(ic, [(344, 712), (SX - SR + 6, SY - 20)], 7)
    rope(ic, [(SX + SR - 8, SY + 10), (SX + SR - 8, 610)], 7)
    shaft(ic)
    kibble(ic, SX + SR - 8, 672)
    rails(ic, 40, 520, 926)
    tub(ic, 300, 500, 810, 900)
    coal_heap(ic, 680, 1016, 982, 680, 38, 8)
