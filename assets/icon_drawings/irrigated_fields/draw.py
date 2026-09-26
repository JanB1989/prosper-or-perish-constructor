"""Irrigated Fields (irrigated_fields): levelled beds between bunds and bright feeder channels, a shaduf.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/irrigated_fields/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/irrigated_fields

Identity: a levelled field block seen from the raised camera, cut into four beds (ripe wheat,
cabbages, young green crops) by low earthen bunds and bright teal feeder channels; a small timber
sluice board where the head channel feeds the middle channel, which spills over the front edge.
At the back left a shaduf (counterweighted lifting pole on two posts) dips its bucket into the
stone-lined well pool that feeds the head channel. Unlike vanilla irrigation_systems (water wheel)
and polders (flat green slab), the water runs as narrow channels between dry crop beds.

Family (irrigation): shares earth, water and timber palette with irrigation_reservoirs, qanats and
jiangnan_hill_terraces.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("irrigation_systems", "polders", "terraces", "farming_village")

# ---- family palette ------------------------------------------------------------------------------
EARTH, EARTH_DK = "#8e7250", "#54402a"
SOIL, SOIL_DK = "#6e5236", "#4a3622"
BUND, BUND_DK = "#a88a5e", "#6e5638"
W_LIGHT, W_DEEP = "#7cc0cc", "#2a6070"
WOOD, WOOD_DK = "#86603e", "#4e3522"
STONE, STONE_DK = "#a8977e", "#6a5c4c"

# ---- field geometry: top plane is a trapezoid, u across (0..1), v depth (0 back .. 1 front) -----
BX0, BX1, BY = 190, 850, 486      # back edge
FX0, FX1, FY = 70, 960, 776       # front edge
FACE = 70                         # front earth face height


def P(u: float, v: float) -> tuple[float, float]:
    xl = BX0 + (FX0 - BX0) * v
    xr = BX1 + (FX1 - BX1) * v
    return (xl + (xr - xl) * u, BY + (FY - BY) * v)


def quad(u0, u1, v0, v1, n: int = 6):
    top = [P(u0 + (u1 - u0) * t, v0) for t in np.linspace(0, 1, n)]
    bot = [P(u0 + (u1 - u0) * t, v1) for t in np.linspace(1, 0, n)]
    return top + bot


def S(v: float) -> float:
    """Perspective scale at depth v."""
    return 0.72 + 0.28 * v


# ---- helpers -------------------------------------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, faint lit edge."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def earth_face(ic: Icon, top_pts, depth: float, c1=EARTH, c2=EARTH_DK) -> Image.Image:
    """Cut earth face hanging below a top edge: strata, clods, pebbles, roots, darker foot."""
    R = ic.random
    bottom = [(x + R.uniform(-3, 3), y + depth + R.uniform(-8, 8)) for x, y in top_pts[::-1]]
    pts = list(top_pts) + bottom
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.3, chroma=0.14)
    lay, d = layer()
    xs = [p[0] for p in pts]
    for k in range(5):
        f = (k + 0.6) / 5.5
        pts_k = [(x, y + depth * f + R.uniform(-3, 3)) for x, y in top_pts]
        d.line(pts_k, fill=(40, 28, 16, 60) if k % 2 else (220, 190, 140, 40), width=R.randint(3, 6))
    for _ in range(int((max(xs) - min(xs)) / 7)):
        x = R.uniform(min(xs), max(xs))
        y0 = np.interp(x, [p[0] for p in top_pts], [p[1] for p in top_pts]) if top_pts[0][0] < top_pts[-1][0] else None
        if y0 is None:
            continue
        y = y0 + R.uniform(6, depth - 6)
        r = R.uniform(4, 11)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 20, 12, 110))
        d.ellipse((x - r * 0.9, y - r * 0.8, x + r * 0.5, y + r * 0.3), fill=(214, 186, 140, 90) if R.random() < 0.5 else (150, 130, 110, 110))
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.poly_mask([(x, y + depth * 0.55) for x, y in top_pts] + bottom)), (20, 14, 8), 0.3, blur=14)
    ic.shade(ic.intersect(m, ic.poly_mask(list(top_pts) + [(x, y + 16) for x, y in top_pts[::-1]])), (255, 236, 196), 0.12, blur=4)
    return m


def channel(ic: Icon, pts, spark: int = 20) -> Image.Image:
    """Narrow water channel between banks: dark wet bank edges, teal water, glints."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m.filter(ImageFilter.MaxFilter(9)), "#4a3a26", "#2e2216", noise=0.2)
    ic.fill(m, W_LIGHT, W_DEEP, (BY - 260, FY + 200), noise=0.08, chroma=0.06)
    R = ic.random
    lay, d = layer()
    for _ in range(spark):
        x, y = R.uniform(min(xs), max(xs)), R.uniform(min(ys), max(ys))
        L = R.uniform(14, 36)
        d.line([(x, y), (x + L, y)], fill=(236, 248, 248, R.randint(120, 200)), width=4)
    composite(ic, lay, m)
    return m


def bund(ic: Icon, pts, w: float) -> None:
    """Low earthen bund along a polyline: lit crest, shaded foot."""
    ic.line(pts, int(w + 8), (70, 52, 32, 200))
    ic.line(pts, int(w), (168, 138, 94))
    ic.line([(x - 1, y - w * 0.22) for x, y in pts], max(3, int(w * 0.35)), (214, 190, 140, 170))


def wheat(ic: Icon, poly, v0: float, v1: float, u0: float, u1: float) -> None:
    """Ripe wheat bed: dense stalks with ears, rows smaller to the back, shaded lower stalks."""
    m = ic.poly_mask(poly)
    ys = [p[1] for p in poly]
    ic.fill(m, "#b08a44", "#6e5024", (min(ys), max(ys)), noise=0.3)
    R = ic.random
    lay, d = layer()
    v = v0 + 0.02
    while v < v1 + 0.02:
        s = S(v)
        xa, ya = P(u0, v)
        xb, yb = P(u1, v)
        d.line([(xa, ya + 2), (xb, yb + 2)], fill=(52, 34, 14, 150), width=int(12 * s))
        u = u0 + R.uniform(0, 0.008)
        while u < u1 - 0.004:
            x, y = P(u, v)
            h = R.uniform(44, 60) * s
            tx = x + R.uniform(-4, 9) * s
            tone = R.uniform(0.82, 1.1)
            d.line([(x, y), (tx, y - h)], fill=(int(128 * tone), int(100 * tone), 42, 240), width=max(3, int(5 * s)))
            ew, eh = 7.5 * s, 19 * s
            d.ellipse((tx - ew, y - h - eh, tx + ew, y - h + eh * 0.6), fill=(int(190 * tone), int(142 * tone), int(56 * tone), 255))
            d.ellipse((tx - ew * 0.85, y - h - eh * 0.9, tx + ew * 0.1, y - h), fill=(236, 200, 118, 170))
            d.line([(tx + ew * 0.3, y - h - eh * 0.6), (tx + ew * 0.5, y - h + eh * 0.4)], fill=(110, 76, 30, 150), width=2)
            u += R.uniform(0.009, 0.014) / s
        v += 0.028
    composite(ic, lay)


def cabbages(ic: Icon, poly, v0, v1, u0, u1, lit=(158, 190, 98), mid=(80, 120, 50), dk=(32, 52, 20), r0=21, step=0.07) -> None:
    """Rows of leafy round plants: dark contact shadow, body, lit top-left cap, pale glint."""
    m = ic.poly_mask(poly)
    ys = [p[1] for p in poly]
    ic.fill(m, SOIL, SOIL_DK, (min(ys), max(ys)), noise=0.32)
    R = ic.random
    lay, d = layer()
    v = v0 + 0.035
    row = 0
    while v < v1 - 0.01:
        s = S(v)
        u = u0 + (0.02 if row % 2 else 0.045) + R.uniform(-0.005, 0.005)
        while u < u1 - 0.02:
            x, y = P(u, v + R.uniform(-0.008, 0.008))
            r = r0 * s * R.uniform(0.75, 1.2)
            d.ellipse((x - r * 1.2, y - r * 0.2, x + r * 1.4, y + r * 0.6), fill=(28, 18, 8, 160))
            d.ellipse((x - r, y - r * 1.1, x + r, y + r * 0.35), fill=dk + (255,))
            d.ellipse((x - r * 0.92, y - r * 1.05, x + r * 0.8, y + r * 0.12), fill=mid + (255,))
            d.ellipse((x - r * 0.78, y - r * 1.0, x + r * 0.12, y - r * 0.38), fill=lit + (230,))
            for a in (200, 250, 300):
                d.arc((x - r * 0.7, y - r * 0.95, x + r * 0.7, y + r * 0.1), a, a + 40, fill=dk + (150,), width=3)
            u += step / s * R.uniform(0.9, 1.15) * 0.75
        v += step * 1.25
        row += 1
    composite(ic, lay)


def sprouts(ic: Icon, poly, v0, v1, u0, u1) -> None:
    """Young green crop in drill rows: tufts of short blades on dark damp soil."""
    m = ic.poly_mask(poly)
    ys = [p[1] for p in poly]
    ic.fill(m, "#5e4630", "#3e2e1c", (min(ys), max(ys)), noise=0.32)
    R = ic.random
    lay, d = layer()
    v = v0 + 0.03
    while v < v1:
        s = S(v)
        xa, ya = P(u0 + 0.01, v)
        xb, yb = P(u1 - 0.01, v)
        d.line([(xa, ya + 4), (xb, yb + 4)], fill=(30, 22, 12, 120), width=int(8 * s))
        u = u0 + 0.015
        while u < u1 - 0.01:
            x, y = P(u, v)
            for _ in range(5):
                h = R.uniform(18, 36) * s
                col = (R.randint(88, 130), R.randint(128, 160), R.randint(48, 70), 240)
                d.line([(x, y), (x + R.uniform(-9, 9) * s, y - h)], fill=col, width=max(3, int(4 * s)))
            u += 0.016 / s
        v += 0.06
    composite(ic, lay)


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["gamma"] = 0.74
    ic.grade["mute"] = 0.82

    # ---- field block: front earth face, then the top plane
    front = [(FX0 + (FX1 - FX0) * t, FY + R.uniform(-2, 2)) for t in np.linspace(0, 1, 24)]
    earth_face(ic, front, FACE)
    top = ic.poly_mask(quad(0, 1, 0, 1))
    ic.fill(top, "#8a6e48", "#6c5234", (BY, FY), noise=0.3)

    # layout (u, v): head channel along the back, middle channel down the centre, cross channel
    HC0, HC1 = 0.03, 0.115          # head channel depth band
    MC0, MC1 = 0.47, 0.545           # middle channel across band
    XC0, XC1 = 0.55, 0.615           # cross channel depth band

    # beds
    beds = [
        (0.03, MC0 - 0.02, HC1 + 0.03, XC0 - 0.025, "sprouts"),
        (MC1 + 0.02, 0.97, HC1 + 0.03, XC0 - 0.025, "cabbage"),
        (0.03, MC0 - 0.02, XC1 + 0.025, 0.97, "wheat"),
        (MC1 + 0.02, 0.97, XC1 + 0.025, 0.97, "wheat_front"),
    ]
    # bund bands between beds and channels (lighter raised earth)
    for u0, u1, v0, v1, _ in beds:
        ic.fill(ic.poly_mask(quad(u0 - 0.018, u1 + 0.018, v0 - 0.02, v1 + 0.02)), BUND, BUND_DK, (BY, FY), noise=0.28)
    # channels
    head = channel(ic, quad(0.3, 1.0, HC0, HC1, 12), 26)
    mid = channel(ic, quad(MC0, MC1, HC0, 1.0, 4), 16)
    cross = channel(ic, quad(0.0, 1.0, XC0, XC1, 12), 22)
    # light running down the middle channel (flow)
    lay, d = layer()
    for v in np.linspace(HC1, 0.98, 7):
        x, y = P((MC0 + MC1) / 2 + R.uniform(-0.01, 0.01), v)
        d.line([(x - 3, y), (x + 3, y + 16)], fill=(240, 250, 250, 170), width=4)
    composite(ic, lay, mid)

    # ---- stone well curb at the head of the channel
    wx0, wx1, wt, wb = 318, 460, 430, 512
    ic.shade(ic.mask("ellipse", (wx0 - 10, wb - 20, wx1 + 60, wb + 26)), alpha=0.4, blur=10)
    curb = union(ic.mask("rectangle", (wx0, wt + 18, wx1, wb)), ic.mask("ellipse", (wx0, wb - 18, wx1, wb + 16)))
    ic.fill(curb, STONE, STONE_DK, (wx0, wx1), vertical=False, noise=0.3)
    lay, d = layer()
    for row, y in enumerate(range(wt + 34, wb + 12, 20)):
        d.line([(wx0, y), (wx1, y + 3)], fill=(60, 48, 36, 150), width=3)
        for x in range(wx0 + (row % 2) * 18, wx1, 36):
            d.line([(x, y - 20), (x, y)], fill=(60, 48, 36, 130), width=3)
    composite(ic, lay, curb)
    ic.shade(ic.intersect(curb, ic.mask("rectangle", (wx0 + 80, 0, SIZE, SIZE))), alpha=0.3, blur=10)
    ic.fill(ic.mask("ellipse", (wx0 - 6, wt, wx1 + 6, wt + 38)), "#b6a68c", "#7a6a56", noise=0.25)
    well = ic.mask("ellipse", (wx0 + 12, wt + 7, wx1 - 12, wt + 32))
    ic.fill(well, "#3c6c78", "#14303a", (wt + 7, wt + 32), noise=0.08)
    lay, d = layer()
    d.polygon([(wx1 - 8, wb - 30), (wx1 + 24, wb - 26), (wx1 + 34, wb + 10), (wx1 - 2, wb + 8)], fill=(200, 232, 236, 220))
    ic.image.alpha_composite(lay)

    # ---- shaduf: two posts, crossbar, long pole with a clay counterweight, rope and bucket
    lx, rx, ptop, pfoot = 200, 256, 268, 506
    ic.shade(ic.poly_mask([(lx - 20, pfoot - 10), (rx + 80, pfoot - 10), (rx + 90, pfoot + 22), (lx - 10, pfoot + 22)]),
             alpha=0.35, blur=10)
    timber(ic, (lx, pfoot), (lx + 8, ptop), 28, "#8a6644", "#4e3624")
    pivot = ((lx + rx) / 2, ptop - 8)
    cw = (70, 350)
    tip = (pivot[0] + (pivot[0] - cw[0]) * 1.45, pivot[1] + (pivot[1] - cw[1]) * 1.45)
    timber(ic, cw, tip, 26, "#9a7450", "#56402a")
    timber(ic, (lx - 14, ptop - 4), (rx + 14, ptop - 10), 22)
    timber(ic, (rx, pfoot + 6), (rx - 6, ptop - 12), 28, "#8a6644", "#4e3624")
    ic.rock(ic.jitter(cw[0] + 4, cw[1] + 12, 52, 42, 9, 0.12), "#8e7258", "#4a3a2a", facets=3)
    ic.line([(cw[0] - 30, cw[1] - 4), (cw[0] + 36, cw[1] + 30)], 6, (60, 44, 26, 200))
    bx, by = tip[0] + 4, wt - 24
    ic.line([tip, (bx, by - 40)], 6, (70, 54, 34))
    bucket = [(bx - 30, by - 42), (bx + 30, by - 42), (bx + 23, by + 8), (bx - 23, by + 8)]
    ic.poly(bucket, "#a67a4c", "#5a3e24", span=(bx - 30, bx + 30), vertical=False, edge=4)
    ic.fill(ic.mask("ellipse", (bx - 30, by - 50, bx + 30, by - 32)), "#3a5a62", "#20343a", noise=0.1)
    ic.line([(bx - 28, by - 24), (bx + 28, by - 24)], 6, (50, 44, 40))
    ic.overlay(lambda d: d.polygon([(bx + 10, by + 4), (bx + 22, by + 4), (bx + 26, wt + 14), (bx + 10, wt + 14)],
                                   fill=(220, 240, 244, 210)))

    for u0, u1, v0, v1, kind in beds:
        poly = quad(u0, u1, v0, v1)
        if kind == "cabbage":
            cabbages(ic, poly, v0, v1, u0, u1)
        elif kind == "sprouts":
            sprouts(ic, poly, v0, v1, u0, u1)
        elif kind == "wheat":
            wheat(ic, poly, v0, v1, u0, u1)
        else:
            cabbages(ic, poly, v0, v1, u0, u1, lit=(170, 184, 96), mid=(118, 140, 60), dk=(56, 70, 28), r0=13, step=0.05)

    # bund crests along the channel edges
    for v in (HC1 + 0.012, XC0 - 0.012, XC1 + 0.012):
        bund(ic, [P(0.0, v), P(MC0 - 0.005, v)], 10 * S(v))
        bund(ic, [P(MC1 + 0.005, v), P(1.0, v)], 10 * S(v))
    for u in (MC0 - 0.01, MC1 + 0.01):
        bund(ic, [P(u, HC1 + 0.01), P(u, XC0 - 0.01)], 8)
        bund(ic, [P(u, XC1 + 0.01), P(u, 0.99)], 9)

    # middle channel spills over the front edge into a small splash
    cx0, _ = P(MC0, 1.0)
    cx1, _ = P(MC1, 1.0)
    lay, d = layer()
    d.polygon([(cx0 + 2, FY - 2), (cx1 - 2, FY - 2), (cx1 + 6, FY + FACE - 10), (cx0 - 6, FY + FACE - 10)], fill=(200, 230, 234, 235))
    for x in np.arange(cx0 + 6, cx1, 9):
        d.line([(x, FY + 2), (x + (x - (cx0 + cx1) / 2) * 0.2, FY + FACE - 14)], fill=(255, 255, 255, 180), width=4)
    ic.image.alpha_composite(lay)

    # ---- sluice board where the head channel feeds the middle channel
    sx0, sy = P(MC0 - 0.02, HC1 + 0.005)
    sx1, _ = P(MC1 + 0.02, HC1 + 0.005)
    for x in (sx0, sx1):
        timber(ic, (x, sy + 6), (x, sy - 60), 16)
    ic.rect((sx0 + 6, sy - 34, sx1 - 6, sy - 2), "#94683f", "#5a3e26", edge=4)
    timber(ic, (sx0 - 10, sy - 58), (sx1 + 10, sy - 60), 12)
    ic.shade(ic.poly_mask([(sx0, sy), (sx1, sy), (sx1 + 20, sy + 30), (sx0 + 20, sy + 30)]), alpha=0.35, blur=8)

    # ---- hoe and a water jar, bottom right on the bund
    jx, jy = 900, 792
    ic.shade(ic.mask("ellipse", (jx - 50, jy - 10, jx + 60, jy + 16)), alpha=0.45, blur=8)
    jar = [(jx - 22, jy - 84), (jx + 22, jy - 84), (jx + 44, jy - 50), (jx + 38, jy - 8), (jx + 14, jy + 4),
           (jx - 14, jy + 4), (jx - 38, jy - 8), (jx - 44, jy - 50)]
    ic.fill(ic.poly_mask(jar), "#c08a5c", "#6a4028", radial=(jx - 30, jy - 70, 110), noise=0.2)
    ic.outline(jar, 4, (50, 30, 18, 180))
    ic.fill(ic.mask("ellipse", (jx - 24, jy - 92, jx + 24, jy - 76)), "#3a2a1e", "#20160e", noise=0.1)
    ic.overlay(lambda d: d.arc((jx - 26, jy - 94, jx + 26, jy - 74), 0, 360, fill=(170, 120, 80, 255), width=6))
    ic.line([(jx - 34, jy - 44), (jx - 26, jy - 60)], 5, (240, 214, 180, 120))

    # soft cast shadow of the wheat towards the lower right and general light from the upper left
    ic.shade(ic.intersect(top, ic.poly_mask([(0, 0), (SIZE, 0), (SIZE, BY + 40), (0, BY + 200)])), (255, 240, 200), 0.06, blur=40)
