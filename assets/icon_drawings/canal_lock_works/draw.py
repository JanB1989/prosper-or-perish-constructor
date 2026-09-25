"""Canal and Lock Works (canal_lock_works): a masonry lock seen side-on, stepping down to the right.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the step in water level. On the left the full lock chamber (high water, a barge waiting);
at the step a heavy timber gate with its balance beam and paddle rack, water jetting through the
paddles into the lower tail on the right. A bypass culvert in the chamber wall pours into the canal
below; the lock-keeper's stone hut stands on the far bank of the tail. Unlike the vanilla
pound_lock icon (gates seen head-on) the lock runs across the picture.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 23
REFS = ("pound_lock_canal_infrastructure", "irrigation_systems", "bridge_infrastructure", "aqueduct_system")

# ---- layout (1024 canvas) ----------------------------------------------------------------------
XL, XS, XR = 120, 560, 920           # left end, the step (lower gate), right end
UG0, UG1 = 100, 150                 # upper gate leaf
LG0, LG1 = 572, 672                 # lower gate leaf, just past the chamber wall end
# upper section (chamber, brim full): far coping top, water top, near kerb top, wall face top
U_FAR, U_WAT, U_KERB, U_FACE = 384, 404, 484, 512
# lower section (tail)
L_FAR, L_WAT, L_KERB, L_FACE = 588, 606, 662, 688
BASE = 736                          # wall foot, standing in the canal
BAND_TOP, BAND_BOT = 690, 800

STONE, STONE_DK = "#a08a70", "#665646"
KERB, KERB_DK = "#c2ae90", "#94806a"
W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
WOOD, WOOD_DK = "#86603e", "#4e3522"


# ---- helpers (candidates for the kit) ----------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(36, 52), width=(70, 150), moss=True) -> None:
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
    # grime streaks running down from the coping
    for _ in range(int((x1 - x0) / 55)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.25, 0.7) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 14), y0, sx + R.uniform(5, 14), y0 + ln))),
                 (35, 30, 22), R.uniform(0.10, 0.2), blur=6)
    # damp darker foot and moss
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - 110, x1, y1 + 40))), (22, 30, 20), 0.42, blur=26)
    if moss:
        for _ in range(int((x1 - x0) / 40)):
            mx = R.uniform(x0, x1)
            my = y1 - R.uniform(10, 90)
            blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(14, 36), R.uniform(8, 18), 8, 0.3)))
            ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)


def kerb(ic: Icon, x0: float, x1: float, top: float, face: float, lip: float = 16) -> None:
    """Coping stones along a wall head: lit top strip, darker front edge, cast shadow under the lip."""
    R = ic.random
    mid = top + (face - top) * 0.45
    ic.fill(ic.mask("rectangle", (x0, top, x1, mid)), KERB, "#ab987c", (x0, x1), vertical=False, noise=0.18)
    ic.fill(ic.mask("rectangle", (x0, mid, x1, face)), "#98826a", "#6e5c4a", (mid, face), noise=0.2)
    x = x0 + R.randint(20, 90)
    while x < x1 - 20:
        ic.line([(x, top + 2), (x, face - 2)], 3, (50, 40, 30, 120))
        x += R.randint(90, 170)
    ic.line([(x0, mid), (x1, mid)], 3, (255, 244, 222, 80))
    ic.shade(ic.mask("rectangle", (x0, face, x1, face + lip)), alpha=0.45, blur=7)


def water_strip(ic: Icon, x0: float, x1: float, y0: float, y1: float, reflect: float = 24) -> Image.Image:
    """Open water seen from the raised camera: lighter far edge, far-wall reflection, sparse ripples."""
    m = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(m, W_LIGHT, W_DEEP, (y0 - 10, y1 + 20), noise=0.08, chroma=0.06)
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


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, vertical_boards: bool = True) -> Image.Image:
    """Board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    lo, hi = (min(xs), max(xs)) if vertical_boards else (min(ys), max(ys))
    v = lo
    while v < hi:
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        col = (255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t))
        if vertical_boards:
            d.rectangle((v, min(ys), v + w, max(ys)), fill=col)
            for _ in range(2):
                gx = v + R.uniform(4, w - 4)
                d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        else:
            d.rectangle((min(xs), v, max(xs), v + w), fill=col)
            gy = v + R.uniform(4, w - 4)
            d.line([(min(xs), gy), (max(xs), gy + R.uniform(-3, 3))], fill=(40, 24, 12, 60), width=2)
            d.line([(min(xs), v), (max(xs), v)], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
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
    ic.shade(ic.poly_mask(lower), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def spout(ic: Icon, x: float, y: float, dx: float, dy: float, w: float = 16) -> None:
    """Water jet leaving an opening at (x, y), arcing by (dx, dy), with a splash where it lands."""
    ts = np.linspace(0, 1, 18)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    lay, d = layer()
    d.line(path, fill=(170, 210, 220, 230), width=int(w + 8), joint="curve")
    d.line(path, fill=(236, 246, 247, 240), width=int(w), joint="curve")
    d.line([(px - 2, py - w * 0.2) for px, py in path[2:]], fill=(255, 255, 255, 170), width=max(3, int(w * 0.3)))
    ex, ey = path[-1]
    for _ in range(12):
        r = ic.random.uniform(4, 10)
        sx, sy = ex + ic.random.uniform(-w * 2.2, w * 2.2), ey + ic.random.uniform(-w * 1.2, w * 0.4)
        d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(240, 248, 248, 210))
    d.ellipse((ex - w * 2.6, ey - w * 0.5, ex + w * 2.6, ey + w * 0.7), fill=(232, 244, 245, 200))
    ic.image.alpha_composite(lay)


# ---- parts -------------------------------------------------------------------------------------
def hut(ic: Icon) -> None:
    """Lock-keeper's hut on the far bank of the tail: rubble walls, tiled roof, chimney."""
    hx0, hx1, eave, ridge, foot = 712, 912, 478, 372, L_FAR + 4
    ic.rect((850, 318, 884, 420), "#9a8c7a", "#6a5f52", vertical=False, edge=4)  # chimney
    ic.rect((842, 306, 892, 324), "#877a69", "#5e544a", edge=4)
    ic.tiles([(hx0 - 24, eave + 8), (hx1 + 20, eave + 8), (hx1 - 8, ridge), (hx0 + 4, ridge)], "#a4684e", "#6a3e2c",
             course=28, stagger=36)
    ashlar(ic, (hx0, eave + 8, hx1, foot), "#c2ad8c", "#8a765c", course=(20, 28), width=(30, 56), moss=False)
    ic.shade(ic.mask("rectangle", (hx0, eave + 8, hx1, eave + 40)), alpha=0.5, blur=9)
    ic.window(746, 510, 780, 544)
    ic.door(836, 504, 884, foot - 2, arched=False, surround=None)
    ic.shade(ic.mask("rectangle", (hx0, foot - 26, hx1, foot)), (25, 30, 18), 0.3, blur=8)


def barge(ic: Icon, bx0: float, bx1: float, gun: float, wl: float) -> Image.Image:
    """Laden river barge waiting in the full chamber; returns the hull mask for the waterline."""
    ts = np.linspace(0, 1, 30)
    top = [(bx0 + (bx1 - bx0) * t, gun + 8 * math.sin(math.pi * t) - 18 * (1 - t) ** 6) for t in ts]
    hull = [(bx0 - 20, gun - 20)] + top + [(bx1 + 6, gun - 2), (bx1 + 4, wl + 14), (bx0 + 30, wl + 14)]
    far = [(x + 6, y - 20) for x, y in top]
    ic.poly(far + top[::-1], "#4c3524", "#35251a", edge=0)  # hold interior over the near gunwale
    L = bx1 - bx0
    for f, h in ((0.22, 60), (0.38, 68), (0.53, 56)):
        ic.sack(bx0 + L * f, gun + 4, 60, h, "#c8b288")
    ic.barrel(bx0 + L * 0.66, gun - 64, bx0 + L * 0.66 + 50, gun + 6)
    ic.barrel(bx0 + L * 0.80, gun - 52, bx0 + L * 0.80 + 44, gun + 8)
    hm = planks(ic, hull, "#8a6440", "#4a3220", board=16, vertical_boards=False)
    ic.shade(ic.intersect(hm, ic.mask("rectangle", (bx0 - 30, wl - 16, bx1 + 10, wl + 20))), alpha=0.4, blur=10)
    ic.shade(ic.intersect(hm, ic.mask("rectangle", (bx1 - 80, 0, SIZE, SIZE))), alpha=0.2, blur=20)
    ic.line(top, 11, (58, 40, 26))
    ic.line([(x, y - 3) for x, y in top], 4, (176, 136, 94, 170))
    ic.outline(hull, 4, (40, 26, 16, 190))
    timber(ic, (bx1 + 4, gun - 4), (bx1 + 12, wl + 6), 13)  # rudder
    timber(ic, (bx1 + 6, gun - 6), (bx1 - 40, gun - 36), 9)  # tiller
    return hm


def gate(ic: Icon, gx0: float, gx1: float, gtop: float, gbot: float, paddles=(), rack: bool = True,
         post_top: float | None = None) -> Image.Image:
    """Mitre-gate leaf seen from downstream: planked, rails and brace, heel post, walkway handrail,
    optional paddle openings and paddle rack with windlass. Returns the leaf mask."""
    w = gx1 - gx0
    planks(ic, [(gx1 - 4, gtop + 14), (gx1 + w * 0.3, gtop + 4), (gx1 + w * 0.3, gbot - 30), (gx1 - 4, gbot - 18)],
           "#5a402c", "#35241a", board=14)  # far leaf beyond the mitre, in shadow
    leaf = [(gx0, gtop), (gx1, gtop + 8), (gx1, gbot), (gx0, gbot - 6)]
    lm = planks(ic, leaf, "#94683f", "#4a3120", board=w / 4)
    n = max(2, int((gbot - gtop) / 110))
    for y in np.linspace(gtop + 12, gbot - 34, n + 1):  # rails
        timber(ic, (gx0 - 2, y), (gx1 + 2, y + 8), 16, "#7c5636", "#4a321f")
    timber(ic, (gx0 + 8, gbot - 40), (gx1 - 8, gtop + 22), 13, "#7c5636", "#4a321f")  # brace
    ic.shade(ic.intersect(lm, ic.mask("rectangle", (gx0 + w * 0.55, 0, SIZE, SIZE))), alpha=0.25, blur=14)
    for px, py in paddles:
        ic.rect((px - 13, py - 12, px + 13, py + 12), "#1f1c18", "#141210", edge=0)
    timber(ic, (gx0 - 10, post_top or gtop - 40), (gx0 - 10, gbot + 6), 26, "#8c6442", "#4e3522")  # heel post
    for x in (gx0 + 10, gx1 - 6):
        timber(ic, (x, gtop + 6), (x, gtop - 54), 10)
    timber(ic, (gx0 - 12, gtop - 52), (gx1 + 8, gtop - 46), 10)
    if rack:
        rx = gx1 - 30
        timber(ic, (rx, gtop + 10), (rx, gtop - 108), 16, "#6f6860", "#3e3a36")
        ic.line([(rx - 6, gtop - 96), (rx - 6, gtop)], 3, (30, 30, 32, 200))
        ic.ellipse((rx - 22, gtop - 126, rx + 20, gtop - 88), "#7a7068", "#403a36", edge=4)
        timber(ic, (rx, gtop - 107), (rx + 50, gtop - 122), 8, "#6a6058", "#3a3632")
    return lm


def balance_beam(ic: Icon, p0, p1, width: float = 34, shadow: bool = True) -> None:
    """Balance beam from the gate head down to the towpath, iron strap and worn end block."""
    if shadow:
        ic.shade(ic.poly_mask([(p0[0] + 12, p0[1] + 30), (p1[0] + 30, p1[1] + 24), (p1[0] + 36, p1[1] + 46),
                               (p0[0] + 26, p0[1] + 48)]), alpha=0.35, blur=10)
    timber(ic, p0, p1, width, "#8e6644", "#523823")
    t = 0.45
    sx, sy = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
    ic.line([(sx - 14, sy - 10), (sx + 14, sy + 12)], 8, (48, 46, 46))
    dx, dy = (p1[0] - p0[0]), (p1[1] - p0[1])
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    timber(ic, (p1[0] - ux * 30, p1[1] - uy * 30), (p1[0] + ux * 10, p1[1] + uy * 10), width + 10, "#7c5838", "#4a321f")


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float, light="#7a8c4c", dark="#2f3f1e", n: int = 16) -> None:
    """Tree crown as one massed shape (union of lumps) with form shading, lit clumps upper left and
    dark pockets lower right; no outlines inside."""
    R = ic.random
    m = Image.new("L", (SIZE, SIZE), 0)
    lumps = []
    for _ in range(n):
        a = R.uniform(0, 2 * math.pi)
        d = R.uniform(0.0, 0.6) ** 0.8
        bx, by = cx + math.cos(a) * rx * d, cy + math.sin(a) * ry * d
        br = min(rx, ry) * R.uniform(0.45, 0.62)
        lumps.append((bx, by, br))
        m = ImageChops.lighter(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.85, 14, 0.07)))
    ic.fill(m, light, dark, radial=(cx - rx * 0.6, cy - ry * 0.7, max(rx, ry) * 2.0), noise=0.3, chroma=0.16)
    for bx, by, br in lumps:  # each lump: lit cap, shaded underside
        cap = ic.poly_mask(ic.jitter(bx - br * 0.25, by - br * 0.3, br * 0.6, br * 0.45, 8, 0.25))
        ic.shade(ic.intersect(cap, m), (220, 235, 150), 0.16, blur=3)
        under = ic.poly_mask(ic.jitter(bx + br * 0.2, by + br * 0.45, br * 0.8, br * 0.35, 8, 0.25))
        ic.shade(ic.intersect(under, m), (8, 18, 6), 0.3, blur=5)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 0.1, cy - ry * 0.1, cx + rx * 1.4, cy + ry * 1.3))),
             (8, 16, 6), 0.3, blur=20)


def tree(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Riverside tree on the far bank: trunk with two limbs, massed crown."""
    base = U_FAR - 16
    timber(ic, (cx + 8, base), (cx, cy + r * 0.2), 24, "#6e5640", "#3a2a1c")
    timber(ic, (cx + 2, cy + r * 0.45), (cx - r * 0.45, cy), 10, "#6e5640", "#3a2a1c")
    timber(ic, (cx + 4, cy + r * 0.5), (cx + r * 0.5, cy + r * 0.05), 9, "#6e5640", "#3a2a1c")
    canopy(ic, cx, cy, r * 1.1, r * 0.8)


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


def draw(ic: Icon) -> None:
    band = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=XL - 36, x1=XR + 36, inset=30, sag=26,
                         light=W_LIGHT, deep=W_DEEP)

    # tail: far bank, hut, far coping, water
    ic.fill(ic.mask("rectangle", (XS, L_FAR - 20, XR, L_FAR)), "#7a864a", "#56632f", noise=0.3)
    hut(ic)
    kerb(ic, XS, XR, L_FAR, L_WAT, lip=0)
    tail = water_strip(ic, XS, XR, L_WAT, L_KERB, reflect=16)

    # chamber: far bank, far coping, water, barge
    ic.fill(ic.mask("rectangle", (XL, U_FAR - 24, XS + 20, U_FAR)), "#7a864a", "#56632f", noise=0.3)
    tree(ic, 240, 286, 108)
    for gx in (150, 300, 470):
        ic.poly(ic.jitter(gx, U_FAR - 20, ic.random.uniform(22, 36), 12, 7, 0.3), "#86924f", "#52602c", edge=0)
    kerb(ic, XL, XS + 20, U_FAR, U_WAT, lip=0)
    water_strip(ic, XL, XS, U_WAT, U_KERB)
    hull = barge(ic, 168, 404, U_WAT + 30, U_KERB - 14)
    ic.fill(ic.intersect(hull, ic.mask("rectangle", (0, U_KERB - 16, SIZE, SIZE))), W_LIGHT, W_DEEP,
            (U_WAT - 10, U_KERB + 20), noise=0.08)
    ic.line([(150, U_KERB - 16), (416, U_KERB - 15)], 5, (225, 240, 242, 170))


    # lower gate at the step, paddles jetting into the tail
    GTOP, GBOT = 318, L_KERB - 16
    gate(ic, LG0, LG1, GTOP, GBOT, paddles=((LG0 + 26, 560), (LG0 + 66, 586)), post_top=GTOP - 70)
    # the gate shades the hut and the tail beyond it (light from the upper left)
    ic.shade(ic.poly_mask([(LG1 + 20, GTOP - 40), (LG1 + 80, GTOP), (LG1 + 90, L_KERB), (LG1, L_KERB)]),
             alpha=0.38, blur=18)
    ic.line([(LG0 + 3, GTOP + 4), (LG0 + 3, GBOT - 8)], 5, (255, 232, 190, 110))  # lit leaf edge
    spout(ic, LG0 + 26, 560, 70, 64, 16)
    spout(ic, LG0 + 66, 586, 80, 44, 14)
    ic.overlay(lambda d: [d.line([(x, L_WAT + 34 + ic.random.uniform(-6, 6)), (x + 26, L_WAT + 34)],
                                 fill=(238, 246, 246, 190), width=7) for x in range(LG1 + 20, LG1 + 150, 24)], tail)

    # near walls standing in the canal, copings on top
    ashlar(ic, (XS, L_FACE, XR, BASE))
    ic.shade(ic.mask("rectangle", (XS, L_FACE, XS + 70, BASE)), alpha=0.45, blur=16)  # shadow of the step
    ashlar(ic, (XL, U_FACE, XS, BASE))
    kerb(ic, XL, XS, U_KERB, U_FACE)
    kerb(ic, XS, XR, L_KERB, L_FACE)
    ic.line([(XS - 3, U_KERB), (XS - 3, BASE)], 5, (255, 244, 222, 90))
    # iron mooring ring and a damp seep down the chamber wall
    ic.overlay(lambda d: d.ellipse((460, 540, 486, 572), outline=(42, 40, 40, 255), width=6))
    ic.shade(ic.mask("rectangle", (500, U_FACE + 4, 530, BASE)), (30, 40, 26), 0.25, blur=8)
    for wx, wy, ww in ((160, U_KERB + 2, 40), (410, U_KERB + 4, 30), (536, U_KERB + 2, 24), (700, L_KERB + 2, 34)):
        weeds(ic, wx, wy, ww)
    for wx, ww in ((150, 50), (420, 40), (640, 44)):
        weeds(ic, wx, U_FAR - 2 if wx < XS else L_FAR - 2, ww, hang=False)

    # bypass culvert in the chamber wall pouring into the canal
    cx0, cx1, cy0 = 250, 320, 620
    mx = (cx0 + cx1) / 2
    ic.fill(ic.mask("ellipse", (cx0 - 20, cy0 - 20, cx1 + 20, cy0 + 70)), "#b4a084", "#7e6c56", noise=0.2)
    ic.fill(ic.mask("rectangle", (cx0 - 20, cy0 + 25, cx1 + 20, BASE)), "#b4a084", "#7e6c56", noise=0.2)
    ic.fill(ic.mask("ellipse", (cx0, cy0, cx1, cy0 + 70)), "#211d19", "#15120f", noise=0.05)
    ic.fill(ic.mask("rectangle", (cx0, cy0 + 35, cx1, BASE)), "#211d19", "#15120f", noise=0.05)
    for a in range(200, 345, 28):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        ic.line([(mx + 36 * ca, cy0 + 36 + 36 * sa), (mx + 56 * ca, cy0 + 36 + 56 * sa)], 3, (40, 32, 24, 150))
    lay, d = layer()
    d.polygon([(cx0 + 4, 676), (cx1 - 4, 676), (cx1 + 14, BASE + 6), (cx0 - 14, BASE + 6)], fill=(210, 232, 236, 235))
    for x in np.arange(cx0 + 8, cx1, 14):
        d.line([(x, 680), (x + (x - mx) * 0.3, BASE)], fill=(255, 255, 255, 170), width=5)
    ic.image.alpha_composite(lay)

    walls = ic.mask("rectangle", (XL, U_FACE, XR, BASE + 60))
    ic.waterline(walls, BASE - 8)
    ic.foam(XL + 20, XR - 30, BASE - 8)
    lay, d = layer()
    for _ in range(16):
        r = ic.random.uniform(7, 14)
        sx, sy = ic.random.uniform(cx0 - 44, cx1 + 44), BASE + ic.random.uniform(-12, 16)
        d.ellipse((sx - r * 1.6, sy - r * 0.6, sx + r * 1.6, sy + r * 0.6), fill=(240, 248, 248, 220))
    composite(ic, lay, band)

    # balance beams reaching out to the towpath
    balance_beam(ic, (LG0 - 6, GTOP - 26), (LG0 - 190, U_KERB + 12), 36)

    # bollard with a rope on the tail coping
    ic.rect((880, L_KERB - 44, 906, L_KERB + 6), "#7a5838", "#46301e", vertical=False, edge=4)
    ic.ellipse((876, L_KERB - 54, 910, L_KERB - 36), "#9a7650", "#5e4228", edge=4)
    ic.line([(893, L_KERB - 26), (852, L_KERB + 2), (812, L_KERB + 8)], 7, (120, 96, 60))
