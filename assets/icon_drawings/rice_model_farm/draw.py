"""Rice Model Farm (rice_model_farm): a levelled grid of paddies cut by a stone-lined canal with a
sluice, survey poles on the bunds, a two-storey estate house and a long tiled granary.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/rice_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/rice_model_farm

Identity: a wide, perfectly levelled block of equal rectangular paddies on straight bunds, all
planted in even rows of green rice, crossed by a straight stone-lined canal with a masonry sluice
gate and a plank footbridge. Red-and-white ranging poles stand on the bund corners and a surveyor's
plane table on its tripod stands at the front right. At the back a two-storey estate house (stone
ground floor, plastered upper floor, tiled hip roof) and a long tiled granary. Tier 4 of the rice
chain: planned, surveyed and run as one estate.

Family (rice): shares the helpers and palette below with rice_farm, rice_farmstead and
rice_rotations (flooded block, rice hills, bunds, thatch, sheaves, seedlings).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

# ---- rice family palette (shared by rice_farm, rice_farmstead, rice_rotations, rice_model_farm) ----
EARTH, EARTH_DK = "#8a6e4c", "#4e3a26"
BUND_C = (132, 110, 70)
BUND_LIT = (150, 164, 96, 190)
W_FAR, W_NEAR = "#88c0be", "#2c6470"
WOOD, WOOD_DK = "#86603e", "#4e3522"
STRAW, STRAW_DK = "#c8a45c", "#7a5a2a"
YOUNG = ((160, 212, 70), (98, 160, 40), (40, 80, 18))
GROWN = ((140, 192, 58), (82, 140, 34), (30, 64, 14))
RIPE = ((204, 150, 48), (154, 104, 30), (84, 56, 16))


# ---- geometry ----------------------------------------------------------------------------------
class Block:
    """Flat field block seen from the raised camera: top plane is a trapezoid.

    u runs across (0 left .. 1 right), v into depth (0 back edge .. 1 front edge)."""

    def __init__(self, bx0, bx1, by, fx0, fx1, fy):
        self.bx0, self.bx1, self.by, self.fx0, self.fx1, self.fy = bx0, bx1, by, fx0, fx1, fy
        self.k = 1.0  # overall size of plants on this block

    def P(self, u, v):
        xl = self.bx0 + (self.fx0 - self.bx0) * v
        xr = self.bx1 + (self.fx1 - self.bx1) * v
        return (xl + (xr - xl) * u, self.by + (self.fy - self.by) * v)

    def s(self, v):
        """Perspective scale at depth v (1 at the front edge)."""
        wb, wf = self.bx1 - self.bx0, self.fx1 - self.fx0
        return (wb + (wf - wb) * v) / wf * self.k

    def quad(self, u0, u1, v0, v1, n=8):
        top = [self.P(u0 + (u1 - u0) * t, v0) for t in np.linspace(0, 1, n)]
        bot = [self.P(u0 + (u1 - u0) * t, v1) for t in np.linspace(1, 0, n)]
        return top + bot

    def band(self, f0, f1, u0=0.0, u1=1.0, n=24):
        """Polygon between two depth boundaries f0(u), f1(u)."""
        us = np.linspace(u0, u1, n)
        return [self.P(u, f0(u)) for u in us] + [self.P(u, f1(u)) for u in us[::-1]]


def const(v):
    return lambda u: v


def wavy(v, amp, freq, phase):
    return lambda u: v + amp * math.sin(freq * u * 2 * math.pi + phase)


# ---- small utilities ---------------------------------------------------------------------------
def layer():
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay, mask=None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def union(a, b):
    return ImageChops.lighter(a, b)


def blank():
    return Image.new("L", (SIZE, SIZE), 0)


def scale_c(c, f):
    return tuple(int(max(0, min(255, v * f))) for v in rgb(c))


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


def post(ic: Icon, x, top, base, w=22, c1="#8a6644", c2="#4e3624") -> None:
    """Round-ish upright pole: lit left edge, dark right edge."""
    ic.rect((x - w / 2, top, x + w / 2, base), c1, c2, vertical=False, noise=0.2, edge=4)


# ---- earth -------------------------------------------------------------------------------------
def earth_face(ic: Icon, top_pts, depth: float, c1=EARTH, c2=EARTH_DK):
    """Cut earth face hanging below a top edge: strata, clods, pebbles, darker foot."""
    R = ic.random
    bottom = [(x + R.uniform(-3, 3), y + depth + R.uniform(-8, 8)) for x, y in top_pts[::-1]]
    pts = list(top_pts) + bottom
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.3, chroma=0.14)
    lay, d = layer()
    for k in range(4):
        f = (k + 0.6) / 4.5
        d.line([(x, y + depth * f + R.uniform(-3, 3)) for x, y in top_pts],
               fill=(40, 28, 16, 60) if k % 2 else (220, 190, 140, 40), width=R.randint(3, 6))
    tx, ty = [p[0] for p in top_pts], [p[1] for p in top_pts]
    for _ in range(int((max(xs) - min(xs)) / 8)):
        x = R.uniform(min(xs), max(xs))
        y = float(np.interp(x, tx, ty)) + R.uniform(6, depth - 6)
        r = R.uniform(4, 10)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 20, 12, 110))
        d.ellipse((x - r * 0.9, y - r * 0.8, x + r * 0.5, y + r * 0.3),
                  fill=(214, 186, 140, 90) if R.random() < 0.5 else (150, 130, 110, 110))
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.poly_mask([(x, y + depth * 0.55) for x, y in top_pts] + bottom)), (20, 14, 8), 0.3, blur=14)
    # wet seepage streaks below the flooded top
    lay, d = layer()
    for _ in range(int((max(xs) - min(xs)) / 60)):
        x = R.uniform(min(xs) + 10, max(xs) - 10)
        y = float(np.interp(x, tx, ty))
        d.line([(x, y + 4), (x + R.uniform(-4, 4), y + depth * R.uniform(0.3, 0.7))], fill=(30, 26, 18, 70), width=R.randint(6, 12))
    composite(ic, lay, m)
    return m


# ---- water and rice ----------------------------------------------------------------------------
def flood(ic: Icon, mask, y0: float, y1: float, far=W_FAR, near=W_NEAR, glints: int = 40) -> None:
    """Shallow flooded paddy: sky reflection lighter at the far edge, muddy blotches, glints."""
    R = ic.random
    ic.fill(mask, far, near, (y0, y1 + 40), noise=0.10, chroma=0.10)
    box = mask.getbbox()
    if not box:
        return
    x0, yy0, x1, yy1 = box
    for _ in range(int((x1 - x0) * (yy1 - yy0) / 9000)):  # silt clouds under the water
        x, y = R.uniform(x0, x1), R.uniform(yy0, yy1)
        r = R.uniform(20, 50)
        ic.shade(ic.intersect(mask, ic.mask("ellipse", (x - r * 1.8, y - r * 0.5, x + r * 1.8, y + r * 0.5))),
                 (92, 78, 46), 0.18, blur=10)
    lay, d = layer()
    for _ in range(glints):
        x, y = R.uniform(x0, x1), R.uniform(yy0, yy1)
        L = R.uniform(20, 60)
        d.line([(x, y), (x + L, y)], fill=(240, 250, 246, R.randint(90, 170)), width=4)
        d.line([(x + 6, y + 6), (x + L - 6, y + 6)], fill=(30, 60, 64, 70), width=3)
    composite(ic, lay, mask)


def tuft(d_ref, d_blade, x: float, y: float, s: float, stage: str, R) -> None:
    """One transplanted rice hill: fan of blades from a point at the water surface.

    ``d_ref`` gets the dark reflection and ripple, ``d_blade`` the blades."""
    if stage == "young":
        n, h, spread, w, pal = R.randint(5, 6), R.uniform(34, 44), 30, 5, YOUNG
    elif stage == "grown":
        n, h, spread, w, pal = R.randint(8, 10), R.uniform(56, 70), 38, 6, GROWN
    else:
        n, h, spread, w, pal = R.randint(8, 10), R.uniform(58, 70), 40, 6, RIPE
    h *= s
    w = max(3, int(round(w * s + 0.4)))
    # reflection and ripple on the water
    d_ref.line([(x, y + 2), (x + R.uniform(-2, 2), y + h * 0.42)], fill=(20, 44, 30, 90), width=int(w * 2.2))
    d_ref.arc((x - 14 * s, y - 4 * s, x + 14 * s, y + 6 * s), 10, 170, fill=(230, 244, 236, 130), width=3)
    lit, mid, dk = pal
    blades = []
    for i in range(n):
        t = (i / (n - 1)) * 2 - 1 if n > 1 else 0
        a = math.radians(t * spread + R.uniform(-8, 8))
        hh = h * R.uniform(0.7, 1.0) * (1 - 0.18 * abs(t))
        tipx = x + math.sin(a) * hh * 0.75 + t * 10 * s
        tipy = y - math.cos(a) * hh
        midp = (x + (tipx - x) * 0.45, y + (tipy - y) * 0.55)
        tip = (tipx + t * 8 * s, tipy + abs(t) * 10 * s)  # tips bend outwards and over
        blades.append((t, midp, tip))
    blades.sort(key=lambda b: -abs(b[0]))  # outer blades first, inner on top
    for t, midp, tip in blades:
        base_col = dk
        top_col = lit if t < -0.15 else (mid if t < 0.35 else tuple(int((m + k) / 2) for m, k in zip(mid, dk)))
        d_blade.line([(x, y), midp], fill=base_col + (255,), width=w + 1)
        d_blade.line([midp, tip], fill=top_col + (255,), width=w)
        d_blade.line([(x + (midp[0] - x) * 0.4, y + (midp[1] - y) * 0.4), midp],
                     fill=tuple(int((a + b) / 2) for a, b in zip(base_col, top_col)) + (255,), width=w)
    if stage == "ripe":  # nodding golden panicles
        for _ in range(R.randint(3, 4)):
            px, py = x + R.uniform(-14, 14) * s, y - h * R.uniform(0.78, 0.98)
            dirx = R.choice((-1, 1))
            pts = [(px, py), (px + dirx * 12 * s, py - 6 * s), (px + dirx * 22 * s, py + 6 * s), (px + dirx * 24 * s, py + 18 * s)]
            d_blade.line(pts, fill=(150, 112, 40, 255), width=max(3, int(4 * s)))
            for k, (gx, gy) in enumerate(pts[1:]):
                r = 5 * s
                d_blade.ellipse((gx - r, gy - r, gx + r, gy + r), fill=(236, 204, 110, 255) if k % 2 == 0 else (206, 164, 70, 255))


def rice(ic: Icon, blk: Block, inside, stage: str, v0: float, v1: float, u0: float = 0.0, u1: float = 1.0,
         dv: float = 0.075, du: float = 0.045, jitter: float = 0.18, clip=None, bclip=None) -> None:
    """Rows of rice hills over [u0,u1] x [v0,v1] where ``inside(u, v)`` holds, back to front."""
    R = ic.random
    ref, dr = layer()
    bl, db = layer()
    v = v0 + dv * 0.5
    row = 0
    while v < v1:
        s = blk.s(v)
        u = u0 + du * (0.3 + 0.5 * (row % 2)) / max(s, 0.3)
        while u < u1:
            uu, vv = u + R.uniform(-jitter, jitter) * du, v + R.uniform(-jitter, jitter) * dv * 0.4
            if inside(uu, vv):
                x, y = blk.P(uu, vv)
                tuft(dr, db, x, y, s, stage, R)
            u += du / max(s, 0.3) * R.uniform(0.9, 1.1)
        v += dv
        row += 1
    composite(ic, ref, clip)
    composite(ic, bl, bclip)


def bund(ic: Icon, pts, w: float, grass: bool = True) -> None:
    """Low earthen bund: cast shadow on the water below it, dark foot, earth body, lit crest, grass."""
    R = ic.random
    ic.overlay(lambda d: d.line([(x + w * 0.35, y + w * 0.55) for x, y in pts], fill=(18, 36, 34, 110), width=int(w * 1.1), joint="curve"))
    ic.line(pts, int(w + 6), (56, 42, 26, 230))
    ic.line(pts, int(w), BUND_C)
    ic.line([(x + 1, y + w * 0.25) for x, y in pts], max(3, int(w * 0.3)), (84, 64, 40, 200))
    ic.line([(x - 1, y - w * 0.22) for x, y in pts], max(3, int(w * 0.38)), BUND_LIT)
    if grass:
        lay, d = layer()
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            seg = math.hypot(xb - xa, yb - ya)
            for _ in range(int(seg / 14)):
                t = R.random()
                x, y = xa + (xb - xa) * t, ya + (yb - ya) * t + R.uniform(-w * 0.35, w * 0.2)
                g = (R.randint(92, 130), R.randint(118, 150), R.randint(52, 70), 200)
                d.line([(x, y), (x + R.uniform(-5, 5), y - R.uniform(6, 12))], fill=g, width=3)
        composite(ic, lay)


def bund_u(blk: Block, f, u0=0.0, u1=1.0, n=24):
    return [blk.P(u, f(u)) for u in np.linspace(u0, u1, n)]


def bund_v(blk: Block, u, v0, v1, n=10):
    return [blk.P(u, v) for v in np.linspace(v0, v1, n)]


# ---- straw, thatch, props ----------------------------------------------------------------------
def thatch(ic: Icon, ridge, eave, c=("#c8a664", "#6e522c"), courses=(0.0, 0.26, 0.5, 0.75, 1.0)) -> None:
    """Thatched roof plane seen from above: overlapping straw courses, straw strokes, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = list(courses)
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 26
        low = []
        for j in range(n + 1):
            t = j / n
            p = rl + (rr - rl) * t + ((el + (er - el) * t) - (rl + (rr - rl) * t)) * min(f1, 1.0)
            low.append((p[0] + rnd.uniform(-4, 4), p[1] + (rnd.uniform(-3, 7) if f1 < 1 else 0)))
        up = [tuple(rl + (el - rl) * f0 + np.array([-40, -4])), tuple(rr + (er - rr) * f0 + np.array([40, -4]))]
        band = ic.intersect(ic.poly_mask(up + low[::-1]), m)
        y0 = (rl + (el - rl) * f0)[1]
        y1 = max(p[1] for p in low)
        if f1 < 1:
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 20) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tint = rnd.uniform(0.92, 1.06)
        ic.fill(band, scale_c(c[0], tint), scale_c(c[1], tint), (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(240):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 24)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 24 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 22)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 20, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 7, (150, 128, 84, 170))


def sheaf(ic: Icon, x: float, base: float, h: float, w: float, lean: float = 0.0) -> None:
    """Standing sheaf of harvested rice: straw butt, tie, flared nodding golden heads, lit left."""
    R = ic.random
    tie = base - h * 0.52
    butt = [(x - w * 0.42, base), (x - w * 0.16, tie), (x + w * 0.16 + lean * 0.3, tie), (x + w * 0.42, base)]
    ic.fill(ic.poly_mask(butt), "#b48c4a", "#6a4c22", radial=(x - w * 0.4, tie, h * 0.7), noise=0.3)
    lay, d = layer()
    for k in range(9):
        bx = x - w * 0.36 + w * 0.72 * k / 8
        d.line([(bx, base - 2), (x + (bx - x) * 0.3, tie)], fill=(90, 62, 26, 110), width=3)
    composite(ic, lay, ic.poly_mask(butt))
    head = ic.jitter(x + lean, tie - h * 0.24, w * 0.58, h * 0.30, 16, 0.12)
    ic.fill(ic.poly_mask(head), "#d8aa4c", "#7a521c", radial=(x - w * 0.45 + lean, tie - h * 0.5, h * 0.75), noise=0.3)
    lay, d = layer()
    for _ in range(26):  # drooping grain heads
        a = R.uniform(-1.3, 1.3)
        px, py = x + lean + math.sin(a) * w * 0.4, tie - h * 0.22 - math.cos(a) * h * 0.24
        dx = math.sin(a) * 18
        d.line([(px, py), (px + dx, py + R.uniform(8, 22))], fill=(236, 196, 96, 200) if a < 0.3 else (130, 90, 30, 200), width=4)
    composite(ic, lay)
    ic.outline(head, 3, (60, 40, 16, 150))
    ic.line([(x - w * 0.2, tie), (x + w * 0.2 + lean * 0.3, tie)], 8, (96, 70, 34))
    ic.shade(ic.mask("ellipse", (x - w * 0.6, base - 10, x + w * 0.8, base + 12)), alpha=0.4, blur=6)


def seedlings(ic: Icon, x: float, y: float, s: float = 1.0) -> None:
    """Tied bundle of rice seedlings lying on a bund: pale roots, green blades."""
    R = ic.random
    lay, d = layer()
    for k in range(12):
        a = R.uniform(-0.25, 0.25)
        L = R.uniform(60, 80) * s
        col = YOUNG[k % 3]
        d.line([(x - 10 * s, y), (x - 10 * s - L * math.cos(a), y - 18 * s - L * math.sin(a))], fill=col + (255,), width=int(5 * s) + 1)
    for k in range(8):
        d.line([(x + 4 * s, y + R.uniform(-6, 6) * s), (x + R.uniform(26, 36) * s, y + R.uniform(-8, 12) * s)],
               fill=(196, 176, 130, 255), width=3)
    composite(ic, lay)
    ic.ellipse((x - 14 * s, y - 12 * s, x + 6 * s, y + 8 * s), "#8a6a40", "#4a361e", edge=3)


def seed_basket(ic: Icon, x0, y0, x1, y1) -> None:
    """Shallow carrying basket heaped with seedling bundles."""
    ic.shade(ic.mask("ellipse", (x0 - 10, y1 - 12, x1 + 20, y1 + 14)), alpha=0.45, blur=8)
    lay, d = layer()
    R = ic.random
    cx = (x0 + x1) / 2
    for k in range(26):
        bx = R.uniform(x0 + 10, x1 - 10)
        a = R.uniform(-0.6, 0.6)
        L = R.uniform(40, 70)
        col = YOUNG[k % 3]
        d.line([(bx, y0 + 10), (bx + math.sin(a) * L, y0 + 10 - math.cos(a) * L)], fill=col + (255,), width=6)
    composite(ic, lay)
    ic.basket(x0, y0, x1, y1)


def paddies(ic: Icon, blk: Block, hb, vs, crops, bw: float = 16, dv: float = 0.075, du: float = 0.045,
            hooks=None, face: float = 70, tint: float = 0.10):
    """A block of flooded paddies: earth front face, water, then bands of rice back to front.

    ``hb`` are the depth boundaries (callables u -> v, first 0, last 1), ``vs[k]`` the inner cross
    bunds of band k (u positions), ``crops[k][j]`` the stage of each cell ('young', 'grown', 'ripe'
    or None for open water), ``hooks[k]`` is called before band k is planted (to place things that
    stand behind it). Returns the top-plane mask."""
    R = ic.random
    hooks = hooks or {}
    front = [blk.P(u, 1.0) for u in np.linspace(0, 1, 24)]
    front = [(x, y + R.uniform(-2, 2)) for x, y in front]
    if face:
        earth_face(ic, front, face)
    top = ic.poly_mask(blk.quad(0, 1, 0, 1, 24))
    flood(ic, top, blk.by, blk.fy)
    for k in range(len(hb) - 1):  # water depth differs cell to cell
        cuts = [0.0] + list(vs[k]) + [1.0]
        for j in range(len(cuts) - 1):
            cell = ic.poly_mask(blk.band(hb[k], hb[k + 1], cuts[j], cuts[j + 1]))
            t = R.uniform(-1, 1)
            ic.shade(cell, (255, 250, 230) if t > 0 else (40, 50, 30), abs(t) * tint, blur=4)
    bund(ic, bund_u(blk, hb[0]), bw * blk.s(0) * 0.9)
    (xl1, y1), (xl0, y0) = blk.P(0, 1), blk.P(0, 0)
    (xr1, _), (xr0, _) = blk.P(1, 1), blk.P(1, 0)
    f = y1 / max(y1 - y0, 1)  # extend the side edges up to the top of the canvas
    walls = ic.poly_mask([(xl1 + (xl0 - xl1) * f - 12, 0), (xr1 + (xr0 - xr1) * f + 12, 0), (xr1 + 12, y1 + 40), (xl1 - 12, y1 + 40)])
    for k in range(len(hb) - 1):
        f0, f1 = hb[k], hb[k + 1]
        if k in hooks:
            hooks[k]()
        cuts = [0.0] + list(vs[k]) + [1.0]
        for u in cuts:
            vm = (f0(u) + f1(u)) / 2
            bund(ic, [blk.P(u, v) for v in np.linspace(f0(u), f1(u), 8)], bw * 0.85 * blk.s(vm))
        for j in range(len(cuts) - 1):
            stage = crops[k][j]
            if not stage:
                continue
            ua, ub = cuts[j], cuts[j + 1]
            mu = 0.022

            def inside(u, v, ua=ua, ub=ub, f0=f0, f1=f1):
                return ua + mu < u < ub - mu and f0(u) + 0.035 < v < f1(u) - 0.004

            vlo = min(f0(ua), f0(ub), f0((ua + ub) / 2)) - 0.03
            vhi = max(f1(ua), f1(ub), f1((ua + ub) / 2)) + 0.03
            rice(ic, blk, inside, stage, vlo, vhi, ua, ub, dv=dv, du=du, clip=top, bclip=walls)
        bund(ic, bund_u(blk, f1), bw * blk.s(1.0 if k == len(hb) - 2 else f1(0.5)) * (1.15 if k == len(hb) - 2 else 1))
    return top


def tree(ic: Icon, cx: float, base: float, h: float, r: float, color=("#5f8a3a", "#1e3212")) -> Image.Image:
    """Leafy tree: tapering trunk with bark mottling, a crown of blobs lit from the upper left,
    leaf dabs and a shaded underside. Returns the crown mask."""
    R = ic.random
    trunk = [(cx - 34, base), (cx - 18, base - h * 0.5), (cx - 15, base - h * 0.8), (cx + 15, base - h * 0.8),
             (cx + 18, base - h * 0.5), (cx + 38, base)]
    ic.poly(trunk, "#8e7862", "#3a2c22", span=(cx - 22, cx + 24), vertical=False, noise=0.26, edge=3)
    for p0, p1, w in (((cx, base - h * 0.55), (cx - r * 0.6, base - h * 0.85), 12),
                      ((cx + 2, base - h * 0.6), (cx + r * 0.5, base - h * 0.9), 11)):
        ic.line([p0, p1], w, (88, 70, 54))
    cy = base - h
    m = blank()
    blobs = []
    for _ in range(26):
        a, d = R.uniform(0, 2 * math.pi), R.random() ** 0.6
        blobs.append((cx + math.cos(a) * r * 0.95 * d, cy + math.sin(a) * r * 0.45 * d, r * R.uniform(0.26, 0.44)))
    blobs.sort(key=lambda b: b[1])
    for bx, by, br in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, br * 1.15, br, 24, 0.08))
        ic.fill(bm, color[0], color[1], radial=(bx - br * 0.8, by - br * 0.9, br * 2.3), noise=0.28, chroma=0.14)
        m = union(m, bm)
    x0, y0, x1, y1 = m.getbbox()

    def dabs(dr):
        for _ in range(int((x1 - x0) * (y1 - y0) / 60)):
            x, y = R.uniform(x0, x1), R.uniform(y0, y1)
            v = (y - cy) / r
            rr = R.uniform(3, 7)
            col = (160, 184, 100, 70) if R.random() < 0.5 - 0.6 * v else (20, 34, 12, 70)
            dr.ellipse((x - rr, y - rr * 0.55, x + rr, y + rr * 0.55), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + r * 0.1, SIZE, SIZE))), (14, 22, 8), 0.40, blur=20)
    return m


def stook(ic: Icon, x: float, base: float, h: float, w: float) -> None:
    """Stook of rice sheaves leaning together: long tied bundles, butts spread on the ground,
    golden heads meeting and nodding at the top. Back sheaves darker, lit from the left."""
    R = ic.random
    ic.shade(ic.mask("ellipse", (x - w * 0.7, base - 12, x + w * 0.9, base + 14)), alpha=0.45, blur=8)
    tops = []
    for k, (off, dark) in enumerate(((-0.12, 0.75), (0.16, 0.72), (-0.42, 0.95), (0.44, 0.88), (0.02, 1.0))):
        bx = x + off * w
        tx, ty = x + off * w * 0.18 + R.uniform(-4, 4), base - h * R.uniform(0.9, 1.0)
        tie = (bx + (tx - bx) * 0.62, base + (ty - base) * 0.62)
        L = math.hypot(tx - bx, ty - base)
        ux, uy = (tx - bx) / L, (ty - base) / L
        nx, ny = -uy, ux
        wb, wt, wh = w * 0.20, w * 0.10, w * 0.20
        pts = [(bx - nx * wb, base - ny * wb), (tie[0] - nx * wt, tie[1] - ny * wt), (tx - nx * wh, ty - ny * wh),
               (tx + nx * wh, ty + ny * wh), (tie[0] + nx * wt, tie[1] + ny * wt), (bx + nx * wb, base + ny * wb)]
        m = ic.poly_mask(pts)
        ic.fill(m, scale_c("#c89a50", dark), scale_c("#6a4a1e", dark), (bx - wb, bx + wb), vertical=False, noise=0.3)
        lay, d = layer()
        for j in range(7):
            f = (j + 0.5) / 7 * 2 - 1
            d.line([(bx + nx * wb * f, base + ny * wb * f), (tx + nx * wh * f, ty + ny * wh * f)],
                   fill=(90, 62, 24, 90) if j % 2 else (236, 204, 130, 70), width=3)
        composite(ic, lay, m)
        ic.outline(pts, 3, (60, 40, 16, 150))
        ic.line([(tie[0] - nx * wt * 1.3, tie[1] - ny * wt * 1.3), (tie[0] + nx * wt * 1.3, tie[1] + ny * wt * 1.3)], 7,
                scale_c((110, 80, 40), dark))
        tops.append((tx, ty, dark))
    lay, d = layer()
    for tx, ty, dark in tops:  # nodding heads spilling over the top
        for _ in range(9):
            side = R.choice((-1, 1))
            sx, sy = tx + R.uniform(-8, 8), ty + R.uniform(-6, 6)
            ex, ey = sx + side * R.uniform(14, 26), sy + R.uniform(10, 26)
            col = (230, 190, 90) if side < 0 else (160, 116, 44)
            d.line([(sx, sy), ((sx + ex) / 2, sy - 6), (ex, ey)], fill=tuple(int(c * dark) for c in col) + (255,), width=5)
    composite(ic, lay)

SEED = 83
REFS = ("farming_village", "polders", "noble_villa", "pound_lock_canal_infrastructure")

PLASTER, PLASTER_DK = "#d2bc94", "#9a8058"
ROOF, ROOF_DK = "#8e5e48", "#4e3026"
STONE, STONE_DK = "#aea08a", "#6e6452"


def manor(ic: Icon) -> None:
    """Two-storey estate house and a long granary, both tiled."""
    R = ic.random
    # long granary on the right, behind the house corner
    gx0, gx1, gtop, gbase = 600, 900, 324, 462
    ic.stonewall((gx0, gtop, gx1, gbase), STONE, STONE_DK, course=24)
    for x in (650, 740, 830):  # ventilation slits
        ic.rect((x, gtop + 34, x + 18, gtop + 84), "#2a2420", "#141010", edge=3)
    ic.door(700, 380, 770, gbase - 2, arched=True, surround=None)
    ic.shade(ic.mask("rectangle", (gx0, gtop, gx1, gtop + 40)), alpha=0.5, blur=10)
    ic.tiles([(570, 342), (930, 342), (890, 238), (626, 238)], ROOF, ROOF_DK, course=24, stagger=28)
    ic.rect((620, 228, 896, 246), "#6e4436", "#3e2620", edge=4)
    ic.shade(ic.poly_mask([(760, 200), (960, 200), (960, 360), (800, 360)]), alpha=0.18, blur=30)
    # house: stone ground floor, plastered upper floor with timber framing, tiled hip roof
    x0, x1 = 196, 612
    ic.stonewall((x0, 336, x1, 466), STONE, STONE_DK, course=26)
    ic.rect((x0 + 6, 214, x1 - 6, 340), PLASTER, PLASTER_DK, noise=0.18, edge=5)
    for x in (x0 + 14, 300, 404, 508, x1 - 14):
        post(ic, x, 214, 340, 18, "#7a5434", "#402a18")
    ic.beam((x0 + 6, 336), (x1 - 6, 336), 16, (96, 66, 42))
    for x in (236, 340, 444, 548):
        ic.window(x, 250, x + 40, 300)
    for x in (236, 548):
        ic.window(x, 378, x + 40, 426)
    ic.door(372, 368, 436, 464, arched=True, surround="#c2b69e")
    ic.shade(ic.mask("rectangle", (x0 + 6, 214, x1 - 6, 262)), alpha=0.5, blur=12)
    ic.shade(ic.mask("rectangle", (x0, 336, x1, 366)), alpha=0.35, blur=8)
    ic.tiles([(150, 236), (658, 236), (560, 78), (248, 78)], ROOF, ROOF_DK, course=26, stagger=30)
    ic.rect((240, 64, 568, 86), "#6e4436", "#3e2620", edge=4)
    ic.rect((470, 24, 506, 70), "#9a8a78", "#5e5448", edge=4)  # chimney
    ic.shade(ic.poly_mask([(420, 40), (700, 40), (700, 250), (480, 250)]), alpha=0.18, blur=36)


def ranging_pole(ic: Icon, x: float, base: float, h: float) -> None:
    """Surveyor's ranging pole: thin staff painted in red and white bands, iron shoe."""
    ic.shade(ic.mask("ellipse", (x - 6, base - 6, x + 30, base + 8)), alpha=0.45, blur=5)
    ic.line([(x, base), (x + 2, base - h)], 13, (40, 28, 20))
    n = 5
    for k in range(n):
        ya, yb = base - h * k / n, base - h * (k + 1) / n
        col = (176, 52, 38) if k % 2 == 0 else (226, 214, 190)
        ic.line([(x, ya - 1), (x + 2, yb + 1)], 8, col)
    ic.line([(x - 2, base - 4), (x - 2, base - h + 4)], 3, (255, 240, 220, 80))


def plane_table(ic: Icon, x: float, base: float) -> None:
    """Surveyor's plane table: tripod, drawing board with a sheet, sighting rule."""
    top = base - 120
    ic.shade(ic.mask("ellipse", (x - 70, base - 14, x + 90, base + 16)), alpha=0.45, blur=8)
    for fx in (x - 60, x + 6, x + 64):
        ic.line([(x, top + 10), (fx, base)], 11, (104, 72, 44))
    board = [(x - 76, top - 6), (x + 70, top - 14), (x + 86, top + 14), (x - 62, top + 22)]
    ic.poly(board, "#9a7450", "#5e4028", edge=4)
    sheet = [(x - 60, top - 4), (x + 58, top - 10), (x + 70, top + 10), (x - 48, top + 16)]
    ic.poly(sheet, "#e6dcc4", "#b8ab8e", edge=3)
    ic.line([(x - 40, top + 8), (x + 10, top - 2), (x + 44, top + 4)], 3, (80, 60, 40, 180))
    ic.line([(x - 50, top - 8), (x + 52, top - 20)], 8, (60, 50, 40))  # alidade
    ic.line([(x - 50, top - 8), (x - 50, top - 30)], 5, (60, 50, 40))
    ic.line([(x + 52, top - 20), (x + 52, top - 42)], 5, (60, 50, 40))


def canal(ic: Icon, blk: Block, v0: float, v1: float) -> None:
    """Straight stone-lined canal across the block: kerbs, water with flow lines, a sluice and a footbridge."""
    R = ic.random
    m = ic.poly_mask(blk.quad(0, 1, v0, v1, 12))
    ic.fill(m, "#4e8e9c", "#1c4450", (blk.P(0, v0)[1], blk.P(0, v1)[1] + 20), noise=0.1)
    lay, d = layer()
    for _ in range(30):
        u = R.uniform(0, 1)
        v = R.uniform(v0 + 0.01, v1 - 0.01)
        x, y = blk.P(u, v)
        L = R.uniform(24, 60)
        d.line([(x, y), (x + L, y)], fill=(236, 248, 248, R.randint(110, 190)), width=4)
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.poly_mask(blk.quad(0, 1, v0, v0 + 0.02, 12))), alpha=0.45, blur=4)
    for v, wd in ((v0, 13), (v1, 16)):  # dressed stone kerbs
        pts = [blk.P(u, v) for u in np.linspace(0, 1, 12)]
        s = blk.s(v)
        ic.line(pts, int(wd * s + 8), (60, 54, 46))
        ic.line(pts, int(wd * s), (150, 138, 118))
        ic.line([(x, y - wd * s * 0.25) for x, y in pts], int(wd * s * 0.35), (190, 178, 156))
        for u in np.arange(0.02, 1, 0.035):
            x, y = blk.P(u + R.uniform(-0.004, 0.004), v)
            ic.line([(x, y - wd * s * 0.45), (x, y + wd * s * 0.45)], 3, (70, 62, 52, 200))
    # plank footbridge at u = 0.2
    fa, fy0 = blk.P(0.18, v0 - 0.01)
    fb, fy1 = blk.P(0.24, v1 + 0.01)
    fa2, _ = blk.P(0.18, v1 + 0.01)
    fb2, _ = blk.P(0.24, v0 - 0.01)
    deck = [(fa, fy0), (fb2, fy0), (fb, fy1), (fa2, fy1)]
    ic.shade(ic.poly_mask([(x + 16, y + 12) for x, y in deck]), alpha=0.4, blur=6)
    ic.poly(deck, "#a07a52", "#6a4a2c", edge=4)
    for t in np.linspace(0.15, 0.85, 5):
        ic.line([(fa + (fa2 - fa) * t - 2, fy0 + (fy1 - fy0) * t), (fb2 + (fb - fb2) * t + 2, fy0 + (fy1 - fy0) * t)], 3, (60, 40, 22, 150))


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["gamma"] = 0.74
    ic.grade["mute"] = 0.86

    blk = Block(150, 876, 470, 20, 1004, 850)
    C0, C1 = 0.28, 0.47
    hb = [const(0.0), const(C0), const(C1), const(0.72), const(1.0)]
    grid = [0.25, 0.5, 0.75]
    vs = [grid, [], grid, grid]
    crops = [["grown"] * 4, [None], ["grown", "grown", "young", "grown"], ["grown", "young", "grown", "grown"]]
    paddies(ic, blk, hb, vs, crops, bw=20, du=0.037, dv=0.085, face=72, tint=0.05,
            hooks={0: lambda: manor(ic), 2: lambda: canal(ic, blk, C0, C1)})

    # ranging poles on bund corners
    for u, v, h in ((0.25, 0.72, 150), (0.75, 0.72, 150), (0.5, 0.0, 120), (1.0, C1, 136)):
        x, y = blk.P(u, v)
        ranging_pole(ic, x, y, h * blk.s(v))
    plane_table(ic, 890, 846)
    ic.shade(ic.poly_mask([(0, 0), (SIZE, 0), (SIZE, 480), (0, 620)]), (255, 244, 214), 0.06, blur=40)
