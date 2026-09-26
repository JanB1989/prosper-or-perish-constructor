"""Canal and Lock Works (canal_lock_works): a masonry lock seen side-on, stepping down to the right.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the step in water level. On the left the upper pound lies brim high between ashlar walls;
at the step one big closed timber gate holds it, its long balance beam reaching back over the
coping; on the right the lower pound lies far below, white water breaking at the gate foot. Level
and square to the viewer like the rest of the waterway works. Unlike the vanilla pound lock (two
gates head-on between stone piers) the lock runs across the picture and the drop carries it.
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 23
REFS = ("pound_lock_canal_infrastructure", "irrigation_systems", "bridge_infrastructure", "aqueduct_system")

# ---- waterways family palette -------------------------------------------------------------------
STONE, STONE_DK = "#a08a70", "#665646"
KERB, KERB_DK = "#c2ae90", "#94806a"
W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
WOOD, WOOD_DK = "#86603e", "#4e3522"
GRASS, GRASS_DK = "#8e9c4e", "#526228"

# ---- layout (1024 canvas) ----------------------------------------------------------------------
XL, XS, XR = 100, 440, 920          # left end, the step (gate heel), right end
GX1 = 700                           # gate mitre edge
# upper pound: far bank top, far coping top, water top, near kerb top, near wall face top
U_BANK, U_FAR, U_WAT, U_KERB, U_FACE = 232, 280, 300, 400, 432
DROP = 190
L_BANK, L_FAR, L_WAT, L_KERB, L_FACE = (v + DROP for v in (U_BANK, U_FAR, U_WAT, U_KERB, U_FACE))
BASE = 760                          # wall foot, standing in the band
BAND_TOP, BAND_BOT = 722, 820
GTOP, GBOT = 228, L_WAT + 84        # gate head, gate foot (in the lower pound)


# ---- helpers ------------------------------------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(36, 52), width=(70, 150), moss=True) -> Image.Image:
    """Weathered ashlar face: per-block tint, soft bevels (lit top/left, dark bottom/right), faint
    mortar, grime streaks from the top, darker damp base with moss. No hard outline per block."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, base, dark, (x0 - 200, x1 + 200), vertical=False, noise=0.22, chroma=0.14)
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
                if R.random() < 0.18:  # chipped corner
                    cx, cy = (bx0 + 6, yb - 6) if R.random() < 0.5 else (bx1 - 6, y + 6)
                    d.ellipse((cx - 7, cy - 6, cx + 7, cy + 6), fill=(40, 30, 22, 90))
            x = xb
        y = yb
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 55)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.25, 0.7) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 14), y0, sx + R.uniform(5, 14), y0 + ln))),
                 (35, 30, 22), R.uniform(0.10, 0.2), blur=6)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - min(110, (y1 - y0) * 0.5), x1, y1 + 40))), (22, 30, 20),
             0.42, blur=24)
    if moss:
        for _ in range(int((x1 - x0) / 40)):
            mx = R.uniform(x0, x1)
            my = y1 - R.uniform(10, min(90, (y1 - y0) * 0.5))
            blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(14, 36), R.uniform(8, 18), 8, 0.3)))
            ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)
    return m


def kerb(ic: Icon, x0: float, x1: float, top: float, face: float, lip: float = 16) -> None:
    """Coping stones along a wall head: lit top strip, darker front edge, cast shadow under the lip."""
    R = ic.random
    mid = top + (face - top) * 0.5
    ic.fill(ic.mask("rectangle", (x0, top, x1, mid)), "#d2c0a2", "#b09c80", (x0, x1), vertical=False, noise=0.18)
    ic.fill(ic.mask("rectangle", (x0, mid, x1, face)), "#98826a", "#6e5c4a", (mid, face), noise=0.2)
    x = x0 + R.randint(20, 90)
    while x < x1 - 20:
        ic.line([(x, top + 2), (x, face - 2)], 3, (50, 40, 30, 120))
        x += R.randint(80, 150)
    ic.line([(x0, top + 3), (x1, top + 3)], 3, (255, 248, 228, 110))
    ic.line([(x0, mid), (x1, mid)], 3, (255, 244, 222, 70))
    if lip:
        ic.shade(ic.mask("rectangle", (x0, face, x1, face + lip)), alpha=0.45, blur=7)


def water_strip(ic: Icon, x0: float, x1: float, y0: float, y1: float, reflect: float = 24,
                light=W_LIGHT, deep=W_DEEP) -> Image.Image:
    """Open water seen from the raised camera: lighter far edge, far-wall reflection, sparse ripples."""
    m = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(m, light, deep, (y0 - 10, y1 + 20), noise=0.08, chroma=0.06)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y0, x1, y0 + reflect))), (30, 42, 40), 0.35, blur=8)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / 2600)):
        y = R.uniform(y0 + reflect * 0.8, y1 - 6)
        x = R.uniform(x0 - 20, x1)
        L = R.uniform(30, 80)
        d.line([(x, y), (x + L, y)], fill=(222, 238, 240, R.randint(90, 160)), width=4)
        d.line([(x + 10, y + 6), (x + L - 6, y + 6)], fill=(20, 45, 58, 90), width=3)
    composite(ic, lay, m)
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
        for _ in range(2):
            gx = v + R.uniform(4, max(5, w - 4))
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
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
    ic.shade(ic.poly_mask(lower), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def turf(ic: Icon, m: Image.Image, light=GRASS, dark=GRASS_DK, density: float = 420) -> None:
    """Grass-covered earth: gradient, short blade strokes lit and shadowed, a few darker patches."""
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, light, dark, (y0, y1), noise=0.3, chroma=0.14)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / density)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        h = R.uniform(8, 20)
        t = R.uniform(-1, 1)
        col = (228, 236, 170, int(60 * t)) if t > 0 else (18, 28, 8, int(-80 * t))
        d.line([(x, y), (x + R.uniform(-5, 5), y - h)], fill=col, width=3)
    composite(ic, lay, m)


def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = True) -> None:
    """Tuft of grass and weeds on a coping, a few blades hanging over the wall face."""
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 34)
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(90, 130), R.randint(110, 140), R.randint(50, 70), 230)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


# ---- parts --------------------------------------------------------------------------------------
def far_bank(ic: Icon, x0: float, x1: float, top: float, bottom: float) -> None:
    """Grassed far bank behind the coping, with a soft uneven top edge."""
    R = ic.random
    xs = np.linspace(x0, x1, 14)
    edge = [(x, top + R.uniform(-5, 5)) for x in xs]
    pts = [(x0, bottom)] + edge + [(x1, bottom)]
    turf(ic, ic.poly_mask(pts))
    ic.outline(pts, 3, (40, 34, 20, 120))
    ic.shade(ic.mask("rectangle", (x0, bottom - 14, x1, bottom + 2)), (20, 30, 12), 0.3, blur=6)
    ic.shade(ic.mask("rectangle", (x0, top - 6, x1, top + 12)), (240, 245, 190), 0.18, blur=6)  # lit brow


def gate(ic: Icon) -> None:
    """One big closed mitre-gate leaf at the step, turned towards the viewer: planked, three rails and
    a brace, heel and mitre posts, walkway with handrail, paddle rack with windlass."""
    x0, x1 = XS, GX1
    skew = 16                                   # the leaf turns away slightly towards the mitre
    far = [(x1 - 6, GTOP + skew + 10), (x1 + 40, GTOP + skew + 2), (x1 + 40, GBOT - 12), (x1 - 6, GBOT - 4)]
    planks(ic, far, "#5e432e", "#35241a", board=14)              # far leaf beyond the mitre, in shade
    leaf = [(x0, GTOP), (x1, GTOP + skew), (x1, GBOT), (x0, GBOT - 6)]
    lm = planks(ic, leaf, "#aa7e4a", "#5a3e26", board=30)
    rails = np.linspace(GTOP + 24, GBOT - 40, 3)
    for y in rails:
        f = (y - GTOP) / (GBOT - GTOP)
        timber(ic, (x0 - 2, y), (x1 + 2, y + skew * (1 - f) + 6 * f), 24, "#8a603a", "#4c3420")
    timber(ic, (x0 + 14, rails[-1] - 8), (x1 - 14, rails[0] + 16), 20, "#8a603a", "#4c3420")  # brace
    # wet dark foot, lit left edge, shade towards the mitre
    ic.shade(ic.intersect(lm, ic.mask("rectangle", (0, GBOT - 90, SIZE, SIZE))), (20, 34, 26), 0.45, blur=16)
    ic.shade(ic.intersect(lm, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, 0, SIZE, SIZE))), alpha=0.18, blur=26)
    ic.line([(x0 + 4, GTOP + 6), (x0 + 4, GBOT - 12)], 5, (255, 232, 190, 110))
    # paddle openings with water spurting through into the lower pound
    for px, py in ((x0 + 80, GBOT - 58), (x1 - 80, GBOT - 50)):
        ic.rect((px - 12, py - 10, px + 12, py + 10), "#1f1c18", "#141210", edge=0)
        lay, d = layer()
        path = [(px + 22 * t, py + 4 + (GBOT - py) * t * t) for t in np.linspace(0, 1, 12)]
        d.line(path, fill=(176, 214, 222, 230), width=18, joint="curve")
        d.line(path, fill=(238, 247, 248, 240), width=11, joint="curve")
        ic.image.alpha_composite(lay)
    # heel post (tall), mitre post
    timber(ic, (x0 - 6, GTOP - 58), (x0 - 6, GBOT + 8), 36, "#936a46", "#523823")
    timber(ic, (x1 + 2, GTOP + skew - 10), (x1 + 2, GBOT + 4), 22, "#86603e", "#4a321f")
    # walkway plank on the head, handrail on posts
    timber(ic, (x0 - 10, GTOP - 6), (x1 + 16, GTOP + skew - 6), 18, "#ae8a62", "#6a4c30")
    for x in (x0 + 90, x0 + 175, x1 - 6):
        t = (x - x0) / (x1 - x0)
        timber(ic, (x, GTOP + skew * t - 10), (x, GTOP + skew * t - 64), 10, "#86603e", "#4e3522")
    timber(ic, (x0 + 80, GTOP + skew * 0.1 - 62), (x1 + 4, GTOP + skew - 62), 10, "#9a724c", "#553a24")
    # paddle rack post and windlass
    rx = x1 - 50
    timber(ic, (rx, GTOP + skew - 6), (rx, GTOP - 100), 18, "#78726a", "#3e3a36")
    ic.ellipse((rx - 24, GTOP - 122, rx + 22, GTOP - 80), "#847a70", "#403a36", edge=4)
    ic.fill(ic.mask("ellipse", (rx - 7, GTOP - 108, rx + 7, GTOP - 94)), "#3a3634", "#1e1c1a", noise=0.05)
    timber(ic, (rx, GTOP - 101), (rx + 54, GTOP - 116), 8, "#6a6058", "#3a3632")


def balance_beam(ic: Icon) -> None:
    """The long balance beam from the gate head back over the upper coping, resting on a trestle."""
    p0, p1 = (XS + 150, GTOP - 22), (XL + 50, U_KERB - 40)
    # shadow on the water and coping below (light from the upper left: falls right and down)
    ic.shade(ic.poly_mask([(p0[0] + 10, U_WAT + 30), (p1[0] + 40, U_KERB + 6), (p1[0] + 50, U_KERB + 30),
                           (p0[0] + 20, U_WAT + 60)]), alpha=0.3, blur=12)
    timber(ic, (p1[0] + 34, U_KERB + 4), (p1[0] + 34, p1[1] + 8), 16, "#6e4e32", "#3e2a1a")  # trestle
    timber(ic, p0, p1, 44, "#a07850", "#573b24")
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    for t in (0.2, 0.55):  # iron straps
        sx, sy = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        ic.line([(sx - uy * 24, sy + ux * 24), (sx + uy * 24, sy - ux * 24)], 8, (48, 46, 46))
    timber(ic, (p1[0] + ux * 50, p1[1] + uy * 50), (p1[0] - ux * 4, p1[1] - uy * 4), 50, "#bea080", "#72563c")


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86
    band = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=XL - 40, x1=XR + 40, inset=30, sag=26,
                         light=W_LIGHT, deep=W_DEEP)

    # lower pound (behind the gate): far bank, far coping, low water
    far_bank(ic, XS, XR, L_BANK, L_FAR + 4)
    kerb(ic, XS, XR, L_FAR, L_WAT, lip=0)
    tail = water_strip(ic, XS, XR, L_WAT, L_KERB, reflect=16, light="#6ea4b6", deep="#2a5a6c")

    # upper pound: far bank, far coping, brim-high water
    far_bank(ic, XL, XS + 20, U_BANK, U_FAR + 4)
    kerb(ic, XL, XS + 20, U_FAR, U_WAT, lip=0)
    water_strip(ic, XL, XS, U_WAT, U_KERB, reflect=20, light="#9accd8", deep="#3e7a8c")

    gate(ic)
    # the gate shades the lower pound to its right
    ic.shade(ic.intersect(tail, ic.poly_mask([(GX1 + 40, L_WAT), (GX1 + 150, L_WAT), (GX1 + 110, L_KERB),
                                              (GX1 + 10, L_KERB)])), alpha=0.3, blur=16)
    # white water breaking at the gate foot and trailing down the pound
    lay, d = layer()
    R = ic.random
    for _ in range(26):
        r = R.uniform(8, 16)
        sx, sy = R.uniform(XS + 10, GX1 + 50), GBOT + R.uniform(-4, 8)
        d.ellipse((sx - r * 1.7, sy - r * 0.5, sx + r * 1.7, sy + r * 0.6), fill=(238, 247, 247, 225))
    for _ in range(10):
        x, y = R.uniform(GX1 + 30, XR - 60), R.uniform(GBOT - 6, L_KERB - 6)
        d.line([(x, y), (x + R.uniform(30, 70), y)], fill=(232, 244, 246, 190), width=6)
    composite(ic, lay, ic.mask("rectangle", (XS, L_WAT, XR, L_KERB)))

    # near walls standing in the band, copings lit on top
    ashlar(ic, (XS, L_FACE, XR, BASE))
    ic.shade(ic.mask("rectangle", (XS, L_FACE, XS + 80, BASE)), alpha=0.4, blur=18)  # shadow of the step
    ashlar(ic, (XL, U_FACE, XS, BASE))
    kerb(ic, XL, XS, U_KERB, U_FACE)
    kerb(ic, XS, XR, L_KERB, L_FACE)
    ic.line([(XS - 3, U_KERB), (XS - 3, BASE)], 6, (30, 22, 15, 150))  # end of the upper wall, turned from the light
    ic.line([(XL + 3, U_KERB + 4), (XL + 3, BASE)], 4, (255, 244, 222, 70))
    ic.overlay(lambda d: d.ellipse((372, 486, 400, 520), outline=(42, 40, 40, 255), width=6))  # mooring ring
    walls = ic.mask("rectangle", (XL, U_FACE, XR, BASE + 60))
    ic.waterline(walls, BASE - 22)
    ic.foam(XL + 10, XR - 10, BASE - 22)

    balance_beam(ic)
    for wx, wy, ww in ((180, U_KERB + 2, 40), (330, U_KERB + 2, 30), (800, L_KERB + 2, 36)):
        weeds(ic, wx, wy, ww)
    rim_darken(ic)
