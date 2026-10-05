"""Paddy Water Control (paddy_water_control): a dragon-backbone chain pump and a timber sluice in a paddy dike.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/paddy_water_control/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/paddy_water_control

Identity: the water works of wet-rice land. A low feeder canal runs along the front; behind it a high
earthen dike holds two flooded paddy tiers set with young green rice. On the left a long wooden
square-pallet chain pump (dragon backbone pump) lies up the dike face from the canal, its pallet chain
running over the trough to a treadle wheel in a post-and-rail frame on the crest, pouring lifted water
into the lower paddy. On the right a timber sluice gate with a stone footing stands in the dike, its
gate raised, letting paddy water out into the canal. Unlike irrigated_fields (dry raised beds, shaduf),
rice_farm (flat paddy block, field shelter) and jiangnan_canal_network (houses and a humped bridge), the
picture is the step in water level between canal and paddy and the two machines that work it.

Family (rice / irrigation): rice palette and rice hills of rice_farm, timber and stone of the waterway
works (canal_lock_works).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 37
REFS = ("irrigation_systems", "polders", "terraces", "farming_village")

# ---- palette (rice family + waterway works) ---------------------------------------------------------
EARTH, EARTH_DK = "#8a6e4c", "#4e3a26"
BUND_C = (132, 110, 70)
BUND_LIT = (150, 164, 96, 190)
W_FAR, W_NEAR = "#a2d4d0", "#3a7680"          # flooded paddy (sky-bright)
C_LIGHT, C_DEEP = "#74aab0", "#28565e"        # canal (darker, greener)
WOOD, WOOD_DK = "#86603e", "#4e3522"
STONE, STONE_DK = "#a08a70", "#665646"
GRASS, GRASS_DK = "#8e9c4e", "#526228"
YOUNG = ((160, 212, 70), (98, 160, 40), (40, 80, 18))
GROWN = ((140, 192, 58), (82, 140, 34), (30, 64, 14))

# ---- layout (1024 canvas) ---------------------------------------------------------------------------
BAND_TOP, BAND_BOT = 744, 850
WL = 776                       # canal water line along the dike foot
CREST = 612                    # front edge of the dike crest
UP_FACE = 34                   # height of the step between the two paddy tiers


# ---- geometry ---------------------------------------------------------------------------------------
class Block:
    """Flat field block seen from the raised camera: top plane is a trapezoid.

    u runs across (0 left .. 1 right), v into depth (0 back edge .. 1 front edge)."""

    def __init__(self, bx0, bx1, by, fx0, fx1, fy, k=1.0):
        self.bx0, self.bx1, self.by, self.fx0, self.fx1, self.fy = bx0, bx1, by, fx0, fx1, fy
        self.k = k

    def P(self, u, v):
        xl = self.bx0 + (self.fx0 - self.bx0) * v
        xr = self.bx1 + (self.fx1 - self.bx1) * v
        return (xl + (xr - xl) * u, self.by + (self.fy - self.by) * v)

    def s(self, v):
        wb, wf = self.bx1 - self.bx0, self.fx1 - self.fx0
        return (wb + (wf - wb) * v) / wf * self.k

    def quad(self, u0, u1, v0, v1, n=8):
        top = [self.P(u0 + (u1 - u0) * t, v0) for t in np.linspace(0, 1, n)]
        bot = [self.P(u0 + (u1 - u0) * t, v1) for t in np.linspace(1, 0, n)]
        return top + bot


# ---- small utilities --------------------------------------------------------------------------------
def layer():
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay, mask=None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def union(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def minus(a, b):
    return ImageChops.subtract(a, b)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> Image.Image:
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
    return m


def post(ic: Icon, x, top, base, w=26, c1="#8a6644", c2="#4e3624") -> None:
    """Round upright pole: lit left edge, dark right edge, weathered top."""
    ic.rect((x - w / 2, top, x + w / 2, base), c1, c2, vertical=False, noise=0.2, edge=4)
    ic.line([(x - w * 0.22, top + 6), (x - w * 0.22, base - 4)], 3, (255, 230, 190, 70))
    ic.fill(ic.mask("ellipse", (x - w / 2, top - w * 0.25, x + w / 2, top + w * 0.25)), "#b89a78", "#7a6048",
            radial=(x - w * 0.2, top - 4, w * 0.6), noise=0.2)


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(30, 44), width=(50, 110), clip=None) -> Image.Image:
    """Weathered ashlar face: per-block tint, soft bevels, faint mortar, damp mossy base."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    if clip is not None:
        m = ic.intersect(m, clip)
    ic.fill(m, base, dark, (x0 - 160, x1 + 160), vertical=False, noise=0.22, chroma=0.14)
    R = ic.random
    lay, d = layer()
    y = y0
    while y < y1:
        yb = min(y + R.randint(*course), y1)
        x = x0 - R.randint(0, width[0])
        while x < x1:
            xb = x + R.randint(*width)
            bx0, bx1 = max(x, x0), min(xb, x1)
            if bx1 - bx0 > 8:
                t = R.uniform(-1, 1)
                d.rectangle((bx0, y, bx1, yb), fill=(255, 240, 215, int(34 * t)) if t > 0 else (30, 22, 14, int(-52 * t)))
                d.line([(bx0 + 4, y + 4), (bx1 - 5, y + 4)], fill=(255, 246, 228, 70), width=4)
                d.line([(bx0 + 4, y + 4), (bx0 + 4, yb - 5)], fill=(255, 246, 228, 40), width=3)
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
            x = xb
        y = yb
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - (y1 - y0) * 0.45, x1, y1 + 40))), (22, 30, 20), 0.4, blur=16)
    for _ in range(int((x1 - x0) / 40)):
        mx = R.uniform(x0, x1)
        my = y1 - R.uniform(8, (y1 - y0) * 0.4)
        blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(12, 28), R.uniform(8, 14), 8, 0.3)))
        ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)
    return m


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        gx = v + R.uniform(4, max(5, w - 4))
        d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def turf(ic: Icon, m, light=GRASS, dark=GRASS_DK, span=None, density: float = 380) -> None:
    """Grass-covered earth: gradient, short blade strokes lit and shadowed."""
    box = m.getbbox()
    if not box:
        return
    x0, y0, x1, y1 = box
    ic.fill(m, light, dark, span or (y0, y1), noise=0.3, chroma=0.14)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / density)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        h = R.uniform(8, 18)
        t = R.uniform(-1, 1)
        col = (228, 236, 170, int(60 * t)) if t > 0 else (18, 28, 8, int(-80 * t))
        d.line([(x, y), (x + R.uniform(-5, 5), y - h)], fill=col, width=3)
    composite(ic, lay, m)


def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = True) -> None:
    """Tuft of grass and weeds, a few blades hanging over an edge."""
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 32)
        down = hang and R.random() < 0.45
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(90, 130), R.randint(110, 140), R.randint(50, 70), 230)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.36) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


# ---- earth ------------------------------------------------------------------------------------------
def earth_face(ic: Icon, top_pts, depth: float, c1=EARTH, c2=EARTH_DK, seep: bool = True):
    """Cut earth face hanging below a top edge: strata, clods, pebbles, darker damp foot."""
    R = ic.random
    bottom = [(x + R.uniform(-3, 3), y + depth + R.uniform(-6, 6)) for x, y in top_pts[::-1]]
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
    if seep:
        lay, d = layer()
        for _ in range(int((max(xs) - min(xs)) / 60)):
            x = R.uniform(min(xs) + 10, max(xs) - 10)
            y = float(np.interp(x, tx, ty))
            d.line([(x, y + 4), (x + R.uniform(-4, 4), y + depth * R.uniform(0.3, 0.7))], fill=(30, 26, 18, 70),
                   width=R.randint(6, 12))
        composite(ic, lay, m)
    return m


# ---- water and rice ---------------------------------------------------------------------------------
def flood(ic: Icon, mask, y0: float, y1: float, far=W_FAR, near=W_NEAR, glints: int = 30) -> None:
    """Shallow flooded paddy: sky reflection lighter at the far edge, silt clouds, glints."""
    R = ic.random
    ic.fill(mask, far, near, (y0, y1 + 60), noise=0.10, chroma=0.10)
    box = mask.getbbox()
    if not box:
        return
    x0, yy0, x1, yy1 = box
    for _ in range(int((x1 - x0) * (yy1 - yy0) / 9000)):
        x, y = R.uniform(x0, x1), R.uniform(yy0, yy1)
        r = R.uniform(20, 50)
        ic.shade(ic.intersect(mask, ic.mask("ellipse", (x - r * 1.8, y - r * 0.5, x + r * 1.8, y + r * 0.5))),
                 (92, 78, 46), 0.16, blur=10)
    lay, d = layer()
    for _ in range(glints):
        x, y = R.uniform(x0, x1), R.uniform(yy0, yy1)
        L = R.uniform(20, 60)
        d.line([(x, y), (x + L, y)], fill=(240, 250, 246, R.randint(90, 170)), width=4)
        d.line([(x + 6, y + 6), (x + L - 6, y + 6)], fill=(30, 60, 64, 70), width=3)
    composite(ic, lay, mask)


def tuft(d_ref, d_blade, x: float, y: float, s: float, stage: str, R) -> None:
    """One transplanted rice hill: fan of blades from a point at the water surface."""
    if stage == "young":
        n, h, spread, w, pal = R.randint(5, 6), R.uniform(34, 44), 30, 5, YOUNG
    else:
        n, h, spread, w, pal = R.randint(7, 9), R.uniform(48, 60), 36, 6, GROWN
    h *= s
    w = max(3, int(round(w * s + 0.4)))
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
        tip = (tipx + t * 8 * s, tipy + abs(t) * 10 * s)
        blades.append((t, midp, tip))
    blades.sort(key=lambda b: -abs(b[0]))
    for t, midp, tip in blades:
        top_col = lit if t < -0.15 else (mid if t < 0.35 else tuple(int((m + k) / 2) for m, k in zip(mid, dk)))
        d_blade.line([(x, y), midp], fill=dk + (255,), width=w + 1)
        d_blade.line([midp, tip], fill=top_col + (255,), width=w)
        d_blade.line([(x + (midp[0] - x) * 0.4, y + (midp[1] - y) * 0.4), midp],
                     fill=tuple(int((a + b) / 2) for a, b in zip(dk, top_col)) + (255,), width=w)


def rice(ic: Icon, blk: Block, inside, stage: str, v0: float, v1: float, u0: float = 0.0, u1: float = 1.0,
         dv: float = 0.11, du: float = 0.042, jitter: float = 0.16, clip=None) -> None:
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
    composite(ic, bl)


def bund(ic: Icon, pts, w: float, grass: bool = True) -> None:
    """Low earthen bund: cast shadow on the water, dark foot, earth body, lit crest, grass."""
    R = ic.random
    ic.overlay(lambda d: d.line([(x + w * 0.35, y + w * 0.55) for x, y in pts], fill=(18, 36, 34, 110),
                                width=int(w * 1.1), joint="curve"))
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


def falls(ic: Icon, x0: float, x1: float, y0: float, y1: float, splash: float = 1.0) -> None:
    """Sheet of water falling over an edge: pale body, streaks, white splash at the foot."""
    R = ic.random
    lay, d = layer()
    d.polygon([(x0, y0), (x1, y0), (x1 + 6, y1), (x0 - 6, y1)], fill=(176, 214, 220, 235))
    for x in np.arange(x0 + 4, x1 - 2, 8):
        d.line([(x, y0 + 2), (x + (x - (x0 + x1) / 2) * 0.12, y1 - 4)], fill=(250, 254, 254, R.randint(150, 220)), width=4)
    for _ in range(int(14 * splash)):
        r = R.uniform(6, 13) * splash
        sx, sy = R.uniform(x0 - 16, x1 + 16), y1 + R.uniform(-8, 8)
        d.ellipse((sx - r * 1.6, sy - r * 0.6, sx + r * 1.6, sy + r * 0.6), fill=(240, 248, 248, 225))
    ic.image.alpha_composite(lay)


# ---- the chain pump ---------------------------------------------------------------------------------
PA, PB = (104, 822), (440, 592)     # trough foot (in the canal) and head (on the crest)


def chain_pump(ic: Icon, wheel_c) -> None:
    """Dragon-backbone pump: a long open timber trough up the dike, square pallets on an endless
    chain (the working run inside the trough, the return run above it), a foot roller in the canal
    and the treadle wheel at the head."""
    R = ic.random
    ax, ay = PA
    bx, by = PB
    L = math.hypot(bx - ax, by - ay)
    dx, dy = (bx - ax) / L, (by - ay) / L
    nx, ny = -dy, dx                       # normal pointing down-right (towards the viewer)

    def at(t, off):
        off *= 1.25                        # trough scale
        return (ax + (bx - ax) * t + nx * off, ay + (by - ay) * t + ny * off)

    # cast shadow of the trough on the dike face (light from the upper left)
    ic.shade(ic.poly_mask([at(0.05, 30), at(1.0, 30), at(1.0, 86), at(0.05, 86)]), alpha=0.38, blur=12)

    # return run of the chain above the trough, carried on a few short trestles
    for t in (0.3, 0.62, 0.9):
        timber(ic, at(t, -14), at(t, -74), 10, "#6e4e32", "#3e2a1a")
    ret = [at(t, -66) for t in np.linspace(0.04, 0.98, 2)]
    ic.line(ret, 9, (52, 40, 30))
    for t in np.arange(0.06, 0.97, 0.062):
        cx, cy = at(t, -66)
        s = 19
        sq = [(cx - dx * 6 - nx * s, cy - dy * 6 - ny * s), (cx + dx * 6 - nx * s, cy + dy * 6 - ny * s),
              (cx + dx * 6 + nx * s, cy + dy * 6 + ny * s), (cx - dx * 6 + nx * s, cy - dy * 6 + ny * s)]
        ic.fill(ic.poly_mask(sq), "#a07a50", "#5a3e26", (cy - s, cy + s), noise=0.2)
        ic.outline(sq, 3, (40, 26, 16, 200))

    # trough: far wall (top edge seen), open channel with water and the working pallets, near side board
    far = [at(t, o) for t, o in ((0, -40), (1, -40), (1, -28), (0, -28))]
    ic.fill(ic.poly_mask(far), "#b48c5e", "#7a5a38", (by - 40, ay), noise=0.2)
    chan = [at(0, -28), at(1, -28), at(1, 0), at(0, 0)]
    cm = ic.poly_mask(chan)
    ic.fill(cm, "#5e9aa4", "#24484e", (by - 40, ay), noise=0.1)
    ic.shade(ic.intersect(cm, ic.poly_mask([at(0, -28), at(1, -28), at(1, -18), at(0, -18)])), (10, 14, 10), 0.45)
    lay, d = layer()
    for t in np.arange(0.03, 1.0, 0.05):
        p0, p1 = at(t, -27), at(t, -1)
        d.line([p0, p1], fill=(70, 48, 28, 255), width=9)
        d.line([(p0[0] - dx * 3, p0[1] - dy * 3), (p1[0] - dx * 3, p1[1] - dy * 3)], fill=(190, 150, 100, 160), width=3)
        g0 = at(t + 0.02, -18)
        d.line([g0, (g0[0] + dx * 10, g0[1] + dy * 10)], fill=(230, 244, 244, 170), width=3)
    composite(ic, lay, cm)
    side = [at(0, 0), at(1, 0), at(1, 44), at(0, 44)]
    sm = ic.poly_mask(side)
    ic.fill(sm, "#a2784c", "#5a3c22", (by, ay + 44), noise=0.2)
    lay, d = layer()
    for off in (14, 29):                    # board joints along the trough
        d.line([at(0, off), at(1, off)], fill=(40, 26, 14, 120), width=3)
    for t in np.arange(0.0, 1.0, 0.11):     # cleats binding the boards
        d.line([at(t, 1), at(t, 43)], fill=(60, 40, 22, 200), width=8)
        d.line([at(t - 0.006, 2), at(t - 0.006, 42)], fill=(214, 176, 124, 90), width=3)
    for _ in range(18):
        t = R.uniform(0, 1)
        d.line([at(t, R.uniform(4, 40)), at(t + R.uniform(0.03, 0.08), R.uniform(4, 40))], fill=(40, 24, 12, 50), width=2)
    composite(ic, lay, sm)
    ic.line([at(0, 1), at(1, 1)], 5, (232, 196, 140, 170))         # lit top edge of the near board
    ic.shade(ic.intersect(sm, ic.poly_mask([at(0, 26), at(1, 26), at(1, 44), at(0, 44)])), (20, 12, 6), 0.3, blur=4)
    ic.outline([at(0, -40), at(1, -40), at(1, 44), at(0, 44)], 4, (40, 26, 16, 200))

    # foot roller in the canal
    fx, fy = at(0.02, -10)
    ic.ellipse((fx - 30, fy - 30, fx + 30, fy + 30), "#8a6644", "#3e2a18", noise=0.2, edge=4)
    ic.fill(ic.mask("ellipse", (fx - 9, fy - 9, fx + 9, fy + 9)), "#3a2a1c", "#1e140c", noise=0.1)

    # head: the chain turns over the treadle wheel; lifted water pours from the trough mouth
    hx, hy = at(1.0, -14)
    falls(ic, hx + 2, hx + 52, hy - 10, hy + 30, splash=1.0)
    wcx, wcy = wheel_c
    treadle_wheel(ic, wcx, wcy)


def treadle_wheel(ic: Icon, cx: float, cy: float, r: float = 80) -> None:
    """Head sprocket with its treadle hub: a ring of spokes ending in foot blocks, iron-bound hub."""
    R = ic.random
    ic.shade(ic.mask("ellipse", (cx - r + 18, cy - r + 22, cx + r + 30, cy + r + 30)), alpha=0.3, blur=14)
    ic.ellipse((cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72), "#7a5636", "#3e2a18", noise=0.2, edge=4)
    ic.shade(ic.intersect(ic.mask("ellipse", (cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72)),
                          ic.mask("ellipse", (cx - r * 0.5, cy - r * 0.5, cx + r * 0.6, cy + r * 0.6))), (20, 12, 6), 0.35)
    for k in range(8):
        a = math.radians(k * 45 + 12)
        p0 = (cx + math.cos(a) * r * 0.2, cy + math.sin(a) * r * 0.2)
        p1 = (cx + math.cos(a) * r, cy + math.sin(a) * r)
        timber(ic, p0, p1, 17, "#9a7450", "#56402a")
        # foot block at the tip, square to the spoke
        tx, ty = -math.sin(a), math.cos(a)
        bw, bh = 22, 11
        ex, ey = p1
        blk = [(ex - tx * bw - math.cos(a) * bh, ey - ty * bw - math.sin(a) * bh),
               (ex + tx * bw - math.cos(a) * bh, ey + ty * bw - math.sin(a) * bh),
               (ex + tx * bw + math.cos(a) * bh, ey + ty * bw + math.sin(a) * bh),
               (ex - tx * bw + math.cos(a) * bh, ey - ty * bw + math.sin(a) * bh)]
        ic.fill(ic.poly_mask(blk), "#b08860", "#6a4a2c", (ey - bw, ey + bw), noise=0.2)
        ic.outline(blk, 3, (40, 26, 16, 210))
    ic.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), "#8a6a48", "#3e2a18", noise=0.2, edge=4)
    ic.overlay(lambda d: d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=(46, 44, 44, 255), width=7))
    ic.fill(ic.mask("ellipse", (cx - 8, cy - 8, cx + 8, cy + 8)), "#2c2420", "#14100c", noise=0.05)
    ic.line([(cx - 16, cy - 10), (cx - 6, cy - 18)], 3, (255, 230, 190, 120))


def thatch_roof(ic: Icon, pts, c1="#d4b272", c2="#7a5c34", course: float = 34) -> Image.Image:
    """Thatched roof plane: straw strands down the slope, broken course edges, weathered blotches."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.26, chroma=0.06)
    lay, d = layer()
    shadow = Image.new("L", (SIZE, SIZE), 0)
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 110)
            yy = y + course + rnd(-6, 6)
            sd.line([(x, yy), (x + seg, yy + rnd(-5, 5))], fill=int(rnd(90, 200)), width=int(rnd(7, 12)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    composite(ic, lay, m)
    ic.shade(ic.intersect(shadow.filter(ImageFilter.GaussianBlur(6)), m), (30, 16, 6), 0.28)
    for _ in range(6):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(24, 60)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44)])
        ic.shade(ic.intersect(ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m), col,
                 rnd(0.08, 0.18), blur=14)
    ic.outline(pts, 5, (40, 26, 12, 220))
    return m


def pump_frame(ic: Icon, x0: float, x1: float, base: float, eave: float, rail: float) -> None:
    """Treadle stand on the crest: two posts, a lean-on rail for the treaders, knee braces, and a
    small hipped thatch canopy against sun and rain."""
    for x, b in ((x0, base), (x1, base - 6)):
        ic.shade(ic.mask("ellipse", (x - 20, b - 8, x + 44, b + 12)), alpha=0.45, blur=6)
    post(ic, x0, eave - 6, base, 26)
    post(ic, x1, eave - 10, base - 6, 26)
    timber(ic, (x0 - 30, rail + 4), (x1 + 30, rail), 20, "#9a7450", "#56402a")
    timber(ic, (x1 - 4, eave + 64), (x1 - 52, eave + 14), 12, "#86603e", "#4e3522")
    timber(ic, (x0 + 4, eave + 64), (x0 + 50, eave + 16), 12, "#86603e", "#4e3522")
    timber(ic, (x0 - 24, eave + 2), (x1 + 24, eave - 2), 18, "#8a6644", "#4e3624")
    roof = [(x0 - 74, eave + 6), (x1 + 78, eave + 2), (x1 - 2, eave - 92), (x0 + 6, eave - 92)]
    ic.shade(ic.poly_mask([(x0 - 40, eave + 6), (x1 + 70, eave + 2), (x1 + 80, eave + 50), (x0 - 20, eave + 54)]),
             alpha=0.4, blur=14)
    thatch_roof(ic, roof)
    lip = [(x0 - 74, eave + 6), (x1 + 78, eave + 2), (x1 + 78, eave + 22), (x0 - 74, eave + 26)]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (eave, eave + 26), noise=0.35)
    ic.overlay(lambda d: [d.line([(x, eave + 4), (x + ic.random.uniform(-3, 3), eave + 24)], fill=(40, 28, 12, 130), width=2)
                          for x in np.arange(x0 - 70, x1 + 76, 7)], ic.poly_mask(lip))
    ic.outline(lip, 4, (40, 26, 12, 200))
    ic.line([(x0 + 4, eave - 94), (x1 - 0, eave - 94)], 16, (104, 84, 50))
    ic.line([(x0 + 4, eave - 96), (x1 - 0, eave - 96)], 6, (160, 136, 88, 170))


# ---- the sluice -------------------------------------------------------------------------------------
def sluice(ic: Icon, x0: float, x1: float, crest: float) -> None:
    """Timber sluice gate in a stone footing set into the dike, raised, paddy water pouring out."""
    R = ic.random
    ox0, ox1 = x0 + 62, x1 - 62          # opening
    otop = crest + 66
    foot = ashlar(ic, (x0, crest + 4, x1, WL + 30))
    ic.outline([(x0, crest + 4), (x1, crest + 4), (x1, WL + 30), (x0, WL + 30)], 4, (40, 30, 22, 200))
    # coping stones on the footing
    ic.rect((x0 - 10, crest - 6, x1 + 10, crest + 12), "#c8b496", "#94806a", edge=4)
    ic.line([(x0 - 6, crest - 2), (x1 + 6, crest - 2)], 3, (255, 248, 228, 110))
    # opening: dark culvert mouth with the outflow
    om = ic.mask("rectangle", (ox0, otop, ox1, WL + 10))
    ic.fill(om, "#1e2220", "#121412", (otop, WL), noise=0.05)
    ic.overlay(lambda d: d.rectangle((ox0, otop, ox1, WL + 10), outline=(30, 24, 18, 230), width=4))
    lay, d = layer()
    d.polygon([(ox0 + 4, otop + 18), (ox1 - 4, otop + 18), (ox1 + 8, WL + 6), (ox0 - 8, WL + 6)], fill=(170, 210, 216, 240))
    for x in np.arange(ox0 + 8, ox1 - 4, 9):
        d.line([(x, otop + 22), (x + (x - (ox0 + ox1) / 2) * 0.25, WL)], fill=(248, 252, 252, R.randint(160, 230)), width=4)
    ic.image.alpha_composite(lay)
    # grooved posts, lintel and the raised gate
    gtop, gbot = crest - 190, otop + 2
    ic.shade(ic.mask("rectangle", (ox0 - 20, gtop + 40, ox1 + 60, otop)), alpha=0.25, blur=14)
    gate = [(ox0 - 4, crest - 92), (ox1 + 4, crest - 92), (ox1 + 4, gbot - 52), (ox0 - 4, gbot - 52)]
    gm = planks(ic, gate, "#aa7e4a", "#5a3e26", board=22)
    ic.shade(ic.intersect(gm, ic.mask("rectangle", (0, gbot - 80, SIZE, SIZE))), (20, 34, 26), 0.4, blur=10)
    timber(ic, (ox0 - 6, crest - 66), (ox1 + 6, crest - 66), 12, "#8a603a", "#4c3420")
    ic.outline(gate, 4, (40, 26, 16, 200))
    for x in (ox0 - 18, ox1 + 18):
        timber(ic, (x, gtop), (x, otop + 2), 30, "#936a46", "#523823")
    timber(ic, (ox0 - 44, gtop + 12), (ox1 + 44, gtop + 8), 26, "#a07850", "#573b24")
    # windlass on the lintel, ropes to the gate
    wy = gtop - 14
    ic.rect((ox0 - 10, wy - 14, ox1 + 10, wy + 14), "#8a6644", "#4a321e", vertical=True, noise=0.2, edge=4)
    ic.line([(ox0 - 6, wy - 6), (ox1 + 6, wy - 6)], 3, (255, 230, 190, 100))
    for x in (ox1 + 22,):
        timber(ic, (x, wy), (x + 26, wy - 34), 10, "#7a5a3a", "#3e2a1a")
    for x in (ox0 + 10, ox1 - 10):
        ic.line([(x, wy + 14), (x, crest - 92)], 4, (70, 56, 40))


def tier(ic: Icon, blk: Block, face: float, cuts, stage: str, dv: float, du: float, notch=None) -> Image.Image:
    """One paddy terrace: earth step face under its front edge, flooded top, cross bunds, rice,
    the front bund; ``notch`` lets water fall over the step at that u."""
    R = ic.random
    top = ic.poly_mask(blk.quad(0, 1, 0, 1, 24))
    flood(ic, top, blk.by, blk.fy, glints=int(14 + (blk.fx1 - blk.fx0) * (blk.fy - blk.by) / 9000))
    ic.shade(ic.intersect(top, ic.mask("rectangle", (0, blk.by, SIZE, blk.by + 18))), (20, 30, 26), 0.35, blur=7)
    front = [blk.P(u, 1.0) for u in np.linspace(0, 1, 24)]
    front = [(x, y + R.uniform(-2, 2)) for x, y in front]
    if face:
        earth_face(ic, front, face + 12)   # runs under the next terrace's back edge
    edges = [0.0] + list(cuts) + [1.0]
    for u in cuts:
        bund(ic, [blk.P(u + 0.015 * (v - 0.5), v) for v in np.linspace(0.02, 1, 6)], 13 * blk.s(0.5))
    for ua, ub in zip(edges[:-1], edges[1:]):
        rice(ic, blk, lambda u, v, ua=ua, ub=ub: ua + 0.03 < u < ub - 0.03 and 0.12 < v < 0.94, stage, 0.0, 1.0,
             ua, ub, dv=dv, du=du, clip=top)
    if notch is not None and face:
        x = blk.P(notch, 1.0)[0]
        bund(ic, [p for p in front if p[0] < x - 22], 15 * blk.s(1))
        bund(ic, [p for p in front if p[0] > x + 22], 15 * blk.s(1))
        falls(ic, x - 18, x + 18, blk.fy - 4, blk.fy + face + 8, splash=0.7)
    return top


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["mute"] = 0.9
    band = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=20, x1=1004, inset=30, sag=24, light=C_LIGHT, deep=C_DEEP)

    # ---- three paddy terraces stepping up behind the dike, back to front
    t3 = Block(250, 800, 300, 206, 846, 362, k=0.62)
    t2 = Block(206, 846, 362 + UP_FACE, 128, 922, 476, k=0.8)
    t1 = Block(128, 922, 476 + UP_FACE, 36, 988, CREST, k=1.0)
    tier(ic, t3, UP_FACE, (0.42,), "grown", 0.5, 0.075, notch=0.2)
    tier(ic, t2, UP_FACE, (0.34, 0.7), "grown", 0.36, 0.068, notch=0.62)

    # ---- dike: front face down to the canal, wide grassy crest
    lo_top = tier(ic, t1, 0, (0.5,), "young", 0.27, 0.06)
    front = [t1.P(u, 1.0) for u in np.linspace(0, 1, 28)]
    front = [(x, y + R.uniform(-2, 2)) for x, y in front]
    face = earth_face(ic, front, WL - CREST + 30)
    grass = ic.intersect(face, ic.poly_mask(list(front) + [(x, y + R.uniform(30, 64)) for x, y in front[::-1]]))
    turf(ic, grass, "#8a9a4a", "#5a6a2c")
    ic.shade(ic.intersect(face, ic.mask("rectangle", (0, CREST + 40, SIZE, CREST + 90))), (20, 14, 8), 0.2, blur=16)
    bund(ic, front, 22)

    # ---- canal water over the dike foot
    ic.waterline(face, WL)
    ic.foam(60, 980, WL - 2)

    # ---- sluice on the right
    sluice(ic, 690, 870, CREST)
    ic.waterline(ic.mask("rectangle", (690, 0, 870, SIZE)), WL + 14)
    lay, d = layer()
    for _ in range(24):
        r = R.uniform(8, 15)
        sx, sy = R.uniform(740, 830), WL + R.uniform(0, 26)
        d.ellipse((sx - r * 1.7, sy - r * 0.55, sx + r * 1.7, sy + r * 0.6), fill=(238, 247, 247, 225))
    for _ in range(8):
        x, y = R.uniform(740, 900), R.uniform(WL + 20, BAND_BOT)
        d.line([(x, y), (x + R.uniform(30, 60), y)], fill=(232, 244, 246, 190), width=6)
    composite(ic, lay, band)

    # ---- chain pump on the left
    pump_frame(ic, 392, 580, CREST + 6, 296, 400)
    chain_pump(ic, (488, 506))
    trough = ic.poly_mask([(PA[0] - 40, PA[1] + 40), (PA[0] + 40, PA[1] - 40), (PA[0] + 140, PA[1] - 40),
                           (PA[0] + 140, PA[1] + 80), (PA[0] - 40, PA[1] + 80)])
    ic.waterline(trough, WL + 22)
    lay, d = layer()
    for _ in range(14):
        r = R.uniform(6, 12)
        sx, sy = R.uniform(PA[0] - 30, PA[0] + 80), WL + 22 + R.uniform(-6, 8)
        d.ellipse((sx - r * 1.7, sy - r * 0.55, sx + r * 1.7, sy + r * 0.6), fill=(238, 247, 247, 210))
    composite(ic, lay, band)

    for wx, wy, ww in ((620, CREST + 2, 40), (930, CREST + 2, 36), (250, CREST + 2, 30)):
        weeds(ic, wx, wy, ww)
    rim_darken(ic)
