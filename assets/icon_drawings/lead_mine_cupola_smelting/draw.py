"""Cupola Lead Mine (lead_mine_cupola_smelting): a reverberatory cupola smelt house with a tall chimney.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/lead_mine_cupola_smelting/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/lead_mine_cupola_smelting

Identity: a long stone smelt house under a blue-grey slate roof with a low brick reverberatory
furnace built against its front (iron buckstays, a glowing fire door), and a tall tapering brick
chimney fed by a flue, its pale fume drifting away. A timber headframe with a sheave wheel over a
deeper shaft stands behind on the left; the heap of cubic galena bottom right and a neat stack of
lead pigs carry the family and show the bigger output.

Local helpers (not in the kit): ``union``, ``tint``, ``cube``, ``cube_heap``, ``limestone`` (shared
with the family), ``stones``, ``shingles``, ``smoke`` (from cookshop), ``bricks``, ``pig``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 31
REFS = ("local_smelters", "iron_foundry", "schwaz_mine", "steel_mill")

GAL = (92, 100, 116)  # galena front face
GAL_LIT = (168, 178, 196)  # galena top face, metallic sheen
GAL_DARK = (30, 34, 42)
LIME = "#d0c2a4"
LIME_DARK = "#7a6c58"
TURF = ("#7e8440", "#434a22")
TIMBER = (116, 78, 48)
IRON = (40, 40, 44)
DARK = (28, 20, 14)


# ---------------------------------------------------------------- helpers
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


def _mix(a, b, t):
    return tuple(int(x * (1 - t) + y * t) for x, y in zip(a, b))


def cube(ic: Icon, cx: float, cy: float, s: float, deg: float = 0.0, k: float = 1.0) -> None:
    """One cubic galena lump seen from the raised front camera: bright top face, lead-grey front,
    dark right side, a sheen line on the lit edges. ``k`` scales the tone."""
    h = s / 2
    kx, ky = h * 0.42, h * 0.62
    j = lambda: ic.random.uniform(-0.07, 0.07) * s  # noqa: E731
    f = [(-h + j(), -h + j()), (h + j(), -h + j()), (h + j(), h + j()), (-h + j(), h + j())]
    top = [f[0], f[1], (f[1][0] + kx, f[1][1] - ky), (f[0][0] + kx, f[0][1] - ky)]
    side = [f[1], top[2], (f[2][0] + kx, f[2][1] - ky), f[2]]
    rot = lambda p: ic.rotate(p, (cx, cy), deg)  # noqa: E731
    f, top, side = rot(f), rot(top), rot(side)
    sc = lambda c: tuple(int(min(255, v * k)) for v in c)  # noqa: E731
    ys = [p[1] for p in top + f]
    ic.fill(ic.poly_mask(top), sc(GAL_LIT), sc(_mix(GAL_LIT, GAL, 0.5)), (min(ys), max(ys)), noise=0.1)
    ic.fill(ic.poly_mask(f), sc(GAL), sc(_mix(GAL, GAL_DARK, 0.55)), (f[0][1], f[3][1]), noise=0.14)
    ic.fill(ic.poly_mask(side), sc(_mix(GAL, GAL_DARK, 0.65)), sc(GAL_DARK), (side[1][1], side[3][1]), noise=0.12)
    if ic.random.random() < 0.5:  # cleavage step on the front face
        y = ic.random.uniform(0.25, 0.7)
        a = (f[0][0] + (f[3][0] - f[0][0]) * y, f[0][1] + (f[3][1] - f[0][1]) * y)
        b = (f[1][0] + (f[2][0] - f[1][0]) * y, f[1][1] + (f[2][1] - f[1][1]) * y)
        ic.line([a, b], 3, (24, 28, 36, 140))
    ic.line([f[3], f[0], f[1]], 3, (220, 230, 245, 120))
    hull = [f[0], top[3], top[2], side[2], f[2], f[3]]
    ic.outline(hull, 4, (22, 24, 30, 200))


def cube_heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float, rows: int) -> None:
    """Mound of cubic galena: dark body, then rows of cubes laid back to front."""
    cx = (x0 + x1) / 2
    body = [(x0, base), (x0 + (cx - x0) * 0.35, base - (base - top) * 0.62), (cx - r * 1.2, top + r * 0.2),
            (cx + r * 0.9, top + r * 0.15), (x1 - (x1 - cx) * 0.3, base - (base - top) * 0.58), (x1, base)]
    ic.poly(body, (66, 72, 84), (22, 24, 30), noise=0.3)
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.55 + (base - top - r * 1.0) * t
        half = (x1 - x0) / 2 * (0.3 + 0.66 * t)
        n = max(1, int(2 * half / (r * 1.2)))
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + ic.random.uniform(-10, 10)
            cube(ic, x, y + ic.random.uniform(-6, 6), r * ic.random.uniform(0.75, 1.1), ic.random.uniform(-24, 24),
                 ic.random.uniform(0.8, 1.08))


def limestone(ic: Icon, pts, beds, turf: float = 34) -> Image.Image:
    """Pale bedded limestone mass: lit top-left, projecting ledges (lit lip, shadow below), sparse
    irregular joints, weathering blotches, dark grimy foot and a turf cap. Returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, LIME, LIME_DARK, radial=(min(xs) + 60, min(ys) - 40, (max(xs) - min(xs)) * 1.05), noise=0.24)
    for _ in range(18):  # weathering: grey, ochre and dark blotches
        x, y = ic.random.uniform(min(xs), max(xs)), ic.random.uniform(min(ys), max(ys))
        r = ic.random.uniform(30, 80)
        col = ic.random.choice([(0, 0, 0), (0, 0, 0), (180, 150, 90), (255, 248, 230), (90, 96, 60)])
        tint(ic, ic.mask("ellipse", (x - r * 1.5, y - r * 0.7, x + r * 1.5, y + r * 0.7)), m, col,
             ic.random.uniform(0.08, 0.2), 16)
    # beds split by joints into big weathered blocks, each shaded as a form (clints and grikes)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    d, sd = ImageDraw.Draw(lay), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    edges = [min(ys) - 40] + list(beds) + [max(ys) + 20]
    for y0, y1 in zip(edges[:-1], edges[1:]):
        x = min(xs) - rnd(0, 120)
        while x < max(xs):
            w = rnd(170, 380)
            j = lambda k=12: rnd(-k, k)  # noqa: E731
            q = [(x + 6 + j(), y0 + 6 + j(4)), (x + w * 0.5, y0 + 6 + j(8)), (x + w - 8 + j(), y0 + 10 + j(6)),
                 (x + w - 8 + j(16), (y0 + y1) / 2), (x + w - 12 + j(), y1 - 8), (x + 10 + j(), y1 - 8 + j(4))]
            t = rnd(-1, 1)
            d.polygon(q, fill=(24, 16, 10, int(-t * 50)) if t < 0 else (255, 244, 220, int(t * 40)))
            d.line([q[0], q[1], q[2]], fill=(255, 246, 228, 110), width=7)  # lit lip of the ledge
            d.line([q[2], q[3], q[4]], fill=(34, 26, 18, 140), width=6)  # joint on the shadow side
            sd.polygon([(x + w - 8, y0 + 14), (x + w + 26, y0 + 34), (x + w + 26, y1), (x + w - 8, y1)], fill=255)
            sd.line([(x, y1 + 10), (x + w, y1 + 10)], fill=255, width=20)  # ledge shadow on the bed below
            x += w
    tint(ic, shadow, m, (20, 14, 10), 0.32, 8)
    grikes = Image.new("L", (ic.size, ic.size), 0)
    gd = ImageDraw.Draw(grikes)
    for y in beds:
        gd.line([(x, y + rnd(-12, 12)) for x in range(-40, ic.size + 80, 50)], fill=255, width=7)
    tint(ic, grikes, m, (30, 24, 18), 0.75)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, ic.mask("rectangle", (max(xs) - 220, 0, ic.size, ic.size)), m, (10, 8, 6), 0.2, 60)
    tint(ic, ic.mask("rectangle", (0, max(ys) - 140, ic.size, ic.size)), m, (46, 44, 26), 0.35, 40)
    # turf cap along the top edge
    top_edge = [p for p in pts if p[1] < max(ys) - 80]
    cap = Image.new("L", (ic.size, ic.size), 0)
    cd = ImageDraw.Draw(cap)
    cd.line(top_edge, fill=255, width=int(turf * 2), joint="curve")
    for p in top_edge[1:-1:2]:  # tufts hanging over the ledge
        cd.ellipse((p[0] - 22, p[1] - 10, p[0] + 22, p[1] + turf * 0.7 + ic.random.uniform(0, 22)), fill=255)
    cap = ic.intersect(cap, m)
    ic.fill(cap, TURF[0], TURF[1], (min(ys), min(ys) + turf * 4), noise=0.4)
    tint(ic, ImageChops.subtract(cap.filter(ImageFilter.MaxFilter(13)), cap), m, (0, 0, 0), 0.5, 4)
    ic.outline(pts)
    return m
SLATE = ("#7a808a", "#3a3e46")
BRICK = ("#a4644a", "#5a3224")


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines (from cookshop)."""
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
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def bricks(ic: Icon, mask: Image.Image, box, colors=BRICK, course: float = 16, brick: float = 40) -> None:
    """Brickwork inside ``mask``: per-brick tone, thin dark mortar courses, stagger; soot-free."""
    x0, y0, x1, y1 = box
    ic.fill(mask, colors[0], colors[1], (x0, x1), vertical=False, noise=0.2, chroma=0.06)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    for k, y in enumerate(np.arange(y0, y1, course)):
        off = (k % 2) * brick / 2
        for x in np.arange(x0 - brick + off, x1, brick):
            t = rnd(-1, 1)
            q = (x + 2, y + 2, x + brick - 2, y + course - 2)
            d.rectangle(q, fill=(20, 8, 4, int(-t * 60)) if t < 0 else (255, 220, 190, int(t * 36)))
            d.line([(x, y), (x, y + course)], fill=(48, 30, 22, 120), width=3)
        d.line([(x0, y), (x1, y)], fill=(48, 30, 22, 130), width=3)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def shingles(ic: Icon, pts, c1, c2, course: float = 30, stagger: float = 40, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping slates: per-slate tone, lit lower lip, soft course shadow (from cookshop)."""
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
            td.polygon(q, fill=(10, 10, 14, int(-t * 60)) if t < 0 else (230, 236, 245, int(t * 40)))
            td.line([(x + w - 2, y + 6), (x + w - 2, y + course - 2)], fill=(20, 22, 28, 90), width=3)
            x += w
        yl = y + course + rnd(-2, 2)
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(225, 232, 240, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (10, 10, 14), 0.5, 3)
    ic.outline(pts, edge)
    return m


def smoke(ic: Icon, puffs, light=("#e6e2da", "#8e8a84")) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath (from cookshop)."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.82 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, light[0], light[1], radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def pig(ic: Icon, x0: float, y0: float, ln: float, h: float, deg: float = 0.0) -> None:
    """Cast lead pig lying on the ground: dull bluish-grey bar, lit top face, rounded ends."""
    d = h * 0.55
    front = [(0, 0), (ln, 0), (ln - h * 0.18, h), (h * 0.18, h)]
    top = [(0, 0), (ln, 0), (ln - d * 0.35, -d), (d * 0.45, -d)]
    fr = ic.rotate(front, (x0, y0), deg)
    tp = ic.rotate(top, (x0, y0), deg)
    ic.fill(ic.poly_mask(tp), (176, 182, 192), (126, 132, 142), (min(p[1] for p in tp), max(p[1] for p in tp)), noise=0.08)
    ic.fill(ic.poly_mask(fr), (112, 118, 128), (58, 62, 70), (x0, x0 + ln), vertical=False, noise=0.1)
    ic.line([fr[0], fr[1]], 3, (228, 234, 242, 150))
    ic.outline(fr[:2] + [fr[2], fr[3]], 4, (26, 28, 34, 200))
    ic.outline([tp[0], tp[3], tp[2], tp[1]], 4, (26, 28, 34, 160))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.97
    BASE = 892
    L, R, EAVE, RIDGE = 176, 668, 560, 404
    CX0, CX1, CTOP = 690, 800, 196  # chimney base span and top

    # ---- fume from the chimney, drifting right
    smoke(ic, [(1000, 136, 34), (954, 132, 46), (896, 140, 54), (840, 164, 52), (790, 184, 40)])

    # ---- headframe over the deep shaft, behind on the left
    for p0, p1, w in (((24, 900), (118, 356), 26), ((210, 900), (130, 356), 26), ((4, 900), (118, 372), 16)):
        ic.beam(p0, p1, w, (100, 68, 42))
    for y in (560, 720):
        ic.beam((24 + (118 - 24) * (900 - y) / 544 - 6, y), (210 - (210 - 130) * (900 - y) / 544 + 6, y), 16,
                (92, 62, 38))
    ic.ellipse((70, 300, 180, 410), "#8a6444", "#4a3220", edge=6)  # sheave wheel
    ic.ellipse((88, 318, 162, 392), "#2a2018", "#1a120c", edge=0)
    for a in np.linspace(0, math.pi, 4, endpoint=False):
        ic.line([(125 + math.cos(a) * 38, 355 + math.sin(a) * 38), (125 - math.cos(a) * 38, 355 - math.sin(a) * 38)],
                7, (110, 78, 50))
    ic.ellipse((114, 344, 136, 366), "#5a5658", "#2a2828", edge=3)
    ic.line([(170, 356), (176, 900)], 6, (60, 46, 30))  # winding rope down to the shaft

    # ---- tall tapering brick chimney (behind the house roof)
    chim = [(CX0, BASE), (CX0 + 20, CTOP + 40), (CX1 - 20, CTOP + 40), (CX1, BASE)]
    cm = ic.poly_mask(chim)
    bricks(ic, cm, (CX0, CTOP, CX1, BASE), course=16, brick=34)
    tint(ic, ic.mask("rectangle", (CX0 + 60, CTOP, CX1 + 10, BASE)), cm, (0, 0, 0), 0.35, 12)
    tint(ic, ic.mask("rectangle", (CX0, CTOP, CX1, CTOP + 110)), cm, (20, 14, 12), 0.5, 20)  # soot
    ic.outline(chim, 5)
    cap = [(CX0 + 8, CTOP + 44), (CX0 + 12, CTOP + 12), (CX1 - 12, CTOP + 12), (CX1 - 8, CTOP + 44)]
    bricks(ic, ic.poly_mask(cap), (CX0, CTOP, CX1, CTOP + 44), course=16, brick=30)
    tint(ic, ic.poly_mask(cap), None, (20, 14, 12), 0.35)
    ic.outline(cap, 5)
    for y in (CTOP + 230, CTOP + 420):  # iron bands
        f = (y - CTOP - 40) / (BASE - CTOP - 40)
        ic.line([(CX0 + 20 - 20 * f - 3, y), (CX1 - 20 + 20 * f + 3, y)], 8, (38, 36, 38))

    # ---- smelt house: slate roof, dressed limestone walls
    roof = [(L - 30, EAVE + 12), (R + 30, EAVE + 12), (R - 20, RIDGE), (L + 24, RIDGE)]
    rmask = shingles(ic, roof, *SLATE, course=28, stagger=38)
    for _ in range(10):
        x, y = ic.random.uniform(L, R), ic.random.uniform(RIDGE, EAVE)
        r = ic.random.uniform(26, 60)
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.5, x + r * 1.4, y + r * 0.5)), rmask,
             ic.random.choice([(0, 0, 0), (220, 228, 236), (96, 104, 60)]), ic.random.uniform(0.08, 0.16), 14)
    tint(ic, ic.mask("rectangle", (R - 160, RIDGE, R + 40, EAVE + 14)), rmask, (0, 0, 0), 0.2, 40)
    ic.poly([(L + 20, RIDGE - 12), (R - 16, RIDGE - 12), (R - 16, RIDGE + 6), (L + 20, RIDGE + 6)], "#6a6e76",
            "#3a3e44", edge=4)
    # roof louvre for the fume
    ic.poly([(330, RIDGE - 4), (330, RIDGE - 56), (420, RIDGE - 56), (420, RIDGE - 4)], "#4a3a2c", "#2a2018", edge=4)
    ic.poly([(318, RIDGE - 52), (369, RIDGE - 92), (432, RIDGE - 52)], "#727882", "#40444c", edge=4)
    ic.shade(ic.mask("ellipse", (330, RIDGE - 120, 420, RIDGE - 60)), (200, 196, 190), 0.0)

    wall = ic.mask("rectangle", (L, EAVE + 12, R, BASE))
    stones(ic, (L, EAVE + 12, R, BASE), "#c0a888", "#7a6650", course=38, clip=wall)
    tint(ic, ic.mask("rectangle", (L, EAVE + 12, R, EAVE + 70)), wall, (0, 0, 0), 0.45, 12)  # eave shadow
    tint(ic, ic.mask("rectangle", (L, BASE - 90, R, BASE)), wall, (40, 44, 20), 0.25, 24)
    ic.outline([(L, EAVE + 12), (R, EAVE + 12), (R, BASE), (L, BASE)], 5)
    ic.door(208, 736, 290, BASE, arched=True, surround="#c2b49c")
    ic.window(336, 636, 380, 690)

    # ---- flue from the furnace into the chimney foot
    flue = [(620, 820), (620, 740), (700, 730), (704, 820)]
    bricks(ic, ic.poly_mask(flue), (610, 720, 710, 830), course=16, brick=32)
    tint(ic, ic.poly_mask(flue), None, (0, 0, 0), 0.25)
    ic.outline(flue, 5)

    # ---- reverberatory furnace against the house front: low brick vault, buckstays, fire door
    FX0, FX1, FTOP = 404, 650, 690
    body = union(ic.mask("rectangle", (FX0, FTOP + 60, FX1, BASE)),
                 ic.mask("chord", (FX0, FTOP, FX1, FTOP + 150), start=180, end=360))
    tint(ic, ic.mask("rectangle", (FX0 - 40, FTOP - 30, FX0 + 10, BASE)), wall, (0, 0, 0), 0.4, 16)
    bricks(ic, body, (FX0, FTOP, FX1, BASE), course=18, brick=38)
    tint(ic, ic.mask("rectangle", (FX0 + 150, FTOP, FX1, BASE)), body, (0, 0, 0), 0.3, 20)
    tint(ic, ic.mask("rectangle", (FX0, FTOP, FX1, FTOP + 50)), body, (20, 14, 10), 0.35, 14)
    tint(ic, ic.mask("chord", (FX0 + 10, FTOP + 4, FX1 - 10, FTOP + 120), start=200, end=300), body,
         (255, 230, 200), 0.3, 6)
    ic.overlay(lambda d: d.arc((FX0, FTOP, FX1, FTOP + 150), 180, 360, fill=(40, 26, 18, 210), width=6))
    ic.line([(FX0, FTOP + 75), (FX0, BASE), (FX1, BASE), (FX1, FTOP + 75)], 6)
    # fire door with a restrained glow
    DX0, DX1 = 450, 530
    door = union(ic.mask("ellipse", (DX0, 770, DX1, 850)), ic.mask("rectangle", (DX0, 810, DX1, 870)))
    ic.fill(door, "#ffcc6a", "#b43c14", radial=((DX0 + DX1) / 2, 850, 70), noise=0.1)
    ic.line([(DX0 - 8, 872), (DX1 + 8, 872)], 12, (40, 38, 40))
    tint(ic, ic.mask("ellipse", (DX0 - 70, 740, DX1 + 70, 930)), body, (255, 130, 50), 0.35, 24)
    ic.overlay(lambda d: d.arc((DX0 - 10, 760, DX1 + 10, 860), 180, 360, fill=(40, 26, 18, 210), width=6))
    ic.rect((566, 818, 616, 846), "#ff9a44", "#b03a14", edge=5)  # working door slit
    for x in (FX0 + 12, 440, 548, 634):  # iron buckstays with tie-bolts
        top = FTOP + 75 - 70 * math.sqrt(max(0.0, 1 - ((x - (FX0 + FX1) / 2) / ((FX1 - FX0) / 2)) ** 2))
        ic.line([(x, top + 6), (x, BASE + 6)], 14, (34, 34, 38))
        ic.line([(x - 3, top + 8), (x - 3, BASE)], 3, (120, 120, 126))
        ic.draw.ellipse((x - 9, top - 2, x + 9, top + 14), fill=(44, 44, 48, 255))
    ic.line([(FX0 - 10, 750), (FX1 + 10, 750)], 10, (34, 34, 38))  # tie-rod over the doors

    # ---- plinth / apron
    ic.poly([(150, BASE + 30), (160, BASE - 4), (840, BASE - 4), (860, BASE + 30)], "#8a7a62", "#5a4c3a", noise=0.3)

    # ---- heap of cubic galena, bottom right
    cube_heap(ic, 790, 1016, 988, 760, 44, 4)

    # ---- neat stack of lead pigs, bottom left
    tint(ic, ic.mask("ellipse", (230, 900, 560, 1000)), None, (0, 0, 0), 0.3, 12)
    for x, y in ((250, 972), (400, 972)):
        pig(ic, x, y, 140, 30)
    for x, y in ((270, 940), (410, 942)):
        pig(ic, x, y, 128, 28, -1)
    pig(ic, 330, 912, 134, 28, 1)
