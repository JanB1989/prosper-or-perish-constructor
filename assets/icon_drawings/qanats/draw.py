"""Qanats (qanats): a desert line of shaft mounds, the gallery beneath them opening into a palm garden.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/qanats/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/qanats

Identity: a broad stretch of desert sand cut open in a shallow ochre section at the front. On the
sand, a line of low doughnut-shaped spoil rings around dark shaft mouths runs on a slight diagonal
from the big mother well (timber windlass) at the back left towards the garden, each ring smaller
than the last. In the cut face the shafts drop to the gallery, whose teal water runs out at the
right into an open channel and a pool in a green oasis garden under two date palms. The
desert-to-oasis contrast is the hook; unlike vanilla oma_falaj (a pipe between stone piers) the
underground line of shafts is the subject.

Family (irrigation): shares earth, water and timber palette with irrigated_fields,
irrigation_reservoirs and jiangnan_hill_terraces.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 29
REFS = ("oma_falaj", "caravanserai", "irrigation_systems", "trans_saharan_trade_outposts")

SAND, SAND_DK = "#d2a060", "#9a6c40"
CUT, CUT_DK = "#cca26a", "#946a42"
W_LIGHT, W_DEEP = "#7cc0cc", "#2a6070"
WOOD, WOOD_DK = "#9a7048", "#5a3e26"
SPOIL, SPOIL_DK = "#fae8ae", "#b89a60"

# ---- layout ------------------------------------------------------------------------------------
PX0, PX1 = 34, 604          # plateau (desert) x range
PB, PF = 392, 612           # plateau back / front y
BOT = 742                   # bottom of the cut face (shallow section)
GX0, GX1 = 582, 990         # garden x range (lower ground on the right)
GB, GF = 530, 716           # garden back / front y
GAL0, GAL1 = (70, 694), (PX1, 712)   # gallery floor, falling gently to the outlet
# mounds: (x, y, size) on a slight diagonal towards the garden, smaller along the line
MOUNDS = ((146, 466, 1.08), (292, 504, 0.9), (418, 542, 0.74), (526, 578, 0.6))


def gal_y(x: float) -> float:
    t = (x - GAL0[0]) / (GAL1[0] - GAL0[0])
    return GAL0[1] + (GAL1[1] - GAL0[1]) * t


# ---- helpers -----------------------------------------------------------------------------------
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
    """Squared beam: lit left/upper half, darker other half, lit edge, soft dark rim."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    if abs(ny) < 0.3 and nx < 0:  # near-vertical beam: shade the right half
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.34)
    ic.line([(x0 - nx * h * 0.5, y0 - ny * h * 0.5), (x1 - nx * h * 0.5, y1 - ny * h * 0.5)], max(3, int(width * 0.25)),
            (255, 226, 176, 90))
    ic.outline(pts, 4, (40, 26, 16, 160))


def sand_ripples(ic: Icon, m: Image.Image, box, n: int) -> None:
    """Wind ripples and pebbles on a sand surface: short curved light/dark stroke pairs."""
    R = ic.random
    x0, y0, x1, y1 = box
    lay, d = layer()
    for _ in range(n):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        L = R.uniform(30, 80)
        d.arc((x, y - 10, x + L, y + 10), 200, 340, fill=(252, 236, 196, 120), width=4)
        d.arc((x + 4, y - 4, x + L + 4, y + 16), 200, 340, fill=(130, 96, 56, 80), width=3)
    for _ in range(n // 2):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        r = R.uniform(3, 7)
        d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(120, 90, 60, 140))
    composite(ic, lay, m)


def strata(ic: Icon, pts, top_y: float, bottom_y: float) -> Image.Image:
    """Shallow cut face in warm ochre: pale and rusty strata bands, gravel, slightly darker foot."""
    R = ic.random
    m = ic.poly_mask(pts)
    xs = [p[0] for p in pts]
    ic.fill(m, CUT, CUT_DK, (top_y, bottom_y + 40), noise=0.26, chroma=0.14)
    lay, d = layer()
    y = top_y + 16
    k = 0
    while y < bottom_y - 8:
        th = R.uniform(10, 18)
        light = k % 2 == 0
        col = (246, 222, 168, 110) if light else (150, 88, 48, 90)
        top = [(x, y + 6 * math.sin(x / 80 + k * 1.7)) for x in np.linspace(min(xs), max(xs), 30)]
        d.polygon(top + [(x, yy + th) for x, yy in top[::-1]], fill=col)
        y += th + R.uniform(10, 18)
        k += 1
    for _ in range(int((max(xs) - min(xs)) * (bottom_y - top_y) / 2600)):
        x, yy = R.uniform(min(xs), max(xs)), R.uniform(top_y + 10, bottom_y - 6)
        r = R.uniform(3, 8)
        d.ellipse((x - r, yy - r * 0.7, x + r, yy + r * 0.7), fill=(70, 46, 24, 110))
        d.ellipse((x - r * 0.8, yy - r * 0.7, x + r * 0.4, yy + r * 0.2), fill=(240, 214, 168, 100))
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, top_y, SIZE, top_y + 12))), (255, 240, 200), 0.3, blur=3)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, bottom_y - 36, SIZE, SIZE))), (40, 24, 10), 0.22, blur=12)
    return m


def mound(ic: Icon, cx: float, cy: float, s: float) -> None:
    """Low irregular doughnut ring of pale spoil around a dark shaft mouth, lit from the upper left."""
    R = ic.random
    rx, ry, h = 92 * s, 36 * s, 20 * s
    ic.shade(ic.mask("ellipse", (cx - rx * 0.8, cy - ry * 0.1, cx + rx * 1.35, cy + ry * 1.6)), (70, 38, 12), 0.55, blur=9)
    body = [(cx + rx * 0.9 * math.cos(a) * R.uniform(0.9, 1.08), cy - h + ry * 0.9 * math.sin(a) * R.uniform(0.9, 1.1))
            for a in np.linspace(math.pi, 2 * math.pi, 12)]
    body += [(cx + rx * math.cos(a) * R.uniform(0.92, 1.06), cy + ry * math.sin(a) * R.uniform(0.9, 1.08))
             for a in np.linspace(0, math.pi, 12)]
    m = ic.poly_mask(body)
    ic.fill(m, SPOIL, SPOIL_DK, radial=(cx - rx * 0.7, cy - h - ry * 0.8, rx * 2.0), noise=0.22, chroma=0.12)
    # outer flank facing the viewer, darker at the lower right
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 1.2, cy - h + ry * 0.2, cx + rx * 1.2, cy + ry * 1.6))),
             (110, 70, 30), 0.25, blur=8)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx + rx * 0.3, 0, SIZE, SIZE))), (90, 56, 24), 0.22, blur=14)
    # the crater: shadowed inner wall on the upper left, lit inner wall lower right, black shaft mouth
    crater = ic.poly_mask(ic.jitter(cx + 2, cy - h, rx * 0.5, ry * 0.52, 12, 0.06))
    ic.fill(crater, "#8e6a40", "#d8b87c", radial=(cx - rx * 0.3, cy - h - ry * 0.4, rx * 0.8), noise=0.2)
    hole = ic.mask("ellipse", (cx - rx * 0.3, cy - h - ry * 0.3, cx + rx * 0.3, cy - h + ry * 0.32))
    ic.fill(hole, "#1e140c", "#0e0a07", noise=0.04)
    ic.shade(ic.intersect(hole, ic.mask("rectangle", (0, cy - h + ry * 0.05, SIZE, SIZE))), (90, 60, 34), 0.3, blur=3)
    lay, d = layer()
    for _ in range(int(9 * s) + 3):  # clods of spoil
        a = R.uniform(0, 2 * math.pi)
        rr = R.uniform(0.62, 0.98)
        x, y = cx + rx * rr * math.cos(a), cy - h * 0.5 + ry * rr * math.sin(a)
        r = R.uniform(4, 8)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(120, 86, 44, 90))
        d.ellipse((x - r * 0.8, y - r * 0.8, x + r * 0.3, y + r * 0.1), fill=(255, 238, 190, 100))
    composite(ic, lay, m)


def frond(ic: Icon, cx: float, cy: float, ang: float, L: float, droop: float, width: float, tone: float) -> None:
    """Soft drooping palm frond: lit upper side, shaded underside, feathered lower fringe, no outline."""
    R = ic.random
    dx, dy = math.cos(ang), math.sin(ang)
    spine = [(cx + dx * L * t, cy + dy * L * t + droop * L * t * t) for t in np.linspace(0, 1, 18)]
    upper, lower = [], []
    for i, (x, y) in enumerate(spine):
        j = min(i + 1, len(spine) - 1)
        k = max(i - 1, 0)
        tx, ty = spine[j][0] - spine[k][0], spine[j][1] - spine[k][1]
        n = math.hypot(tx, ty) or 1
        nx, ny = ty / n, -tx / n
        if ny > 0:
            nx, ny = -nx, -ny   # (nx, ny) points up: the lit side
        t = i / (len(spine) - 1)
        w = width * math.sin(math.pi * min(1.0, 0.12 + t * 1.02)) ** 0.7 + 2
        upper.append((x + nx * w * 0.4, y + ny * w * 0.4))
        f = R.uniform(0.75, 1.15) if i % 2 else 0.8
        lower.append((x - nx * w * f + dx * 6, y - ny * w * f + 6))
    m = ic.poly_mask(upper + lower[::-1])
    lit = tuple(int(c * tone) for c in (160, 188, 104))
    dark = tuple(int(c * tone) for c in (58, 86, 38))
    ys = [p[1] for p in upper + lower]
    ic.fill(m, lit, dark, (min(ys) - 10, max(ys) + 10), noise=0.2, chroma=0.1)
    ic.shade(ic.intersect(m, ic.poly_mask(spine + lower[::-1])), (18, 34, 12), 0.3, blur=2)
    lay, d = layer()
    for i in range(2, len(spine) - 1, 2):  # leaflet hints, faint
        x, y = spine[i]
        lx, ly = lower[i]
        d.line([(x, y), (lx + dx * 8, ly + 4)], fill=(28, 46, 20, 70), width=3)
    d.line(spine, fill=(200, 214, 140, 90), width=3)
    composite(ic, lay, m)


def palm(ic: Icon, base, top, lean: float = 0.0, size: float = 150) -> None:
    """Date palm: ringed trunk curving up to a crown of soft drooping fronds and date clusters."""
    R = ic.random
    (bx, by), (tx, ty) = base, top
    pts = []
    for t in np.linspace(0, 1, 22):
        pts.append((bx + (tx - bx) * t + lean * math.sin(math.pi * t), by + (ty - by) * t))
    ic.shade(ic.mask("ellipse", (bx - 30, by - 8, bx + 60, by + 14)), (30, 20, 8), 0.45, blur=6)
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        w = 26 - 8 * i / len(pts)
        seg = [(x0 - w / 2, y0), (x0 + w / 2, y0), (x1 + w / 2, y1 - 2), (x1 - w / 2, y1 - 2)]
        ic.fill(ic.poly_mask(seg), "#b09470", "#5a4634", (x0 - w / 2, x0 + w / 2), vertical=False, noise=0.25)
        ic.line([(x0 - w / 2, y0), (x0 + w / 2, y0 + 3)], 3, (60, 44, 28, 110))
    cx, cy = pts[-1]
    # back fronds (pointing up and back), darker, first
    specs = [(-2.3, 0.9, 0.62), (-1.75, 0.75, 0.7), (-1.2, 0.85, 0.66), (-0.75, 0.9, 0.72),
             (-2.9, 1.0, 0.8), (-0.2, 1.0, 0.84), (3.0, 0.9, 0.96), (0.25, 0.85, 1.0), (2.55, 0.7, 0.92), (0.8, 0.6, 1.02)]
    for ang, lf, tone in specs:
        ang += R.uniform(-0.12, 0.12)
        L = size * lf * R.uniform(0.9, 1.08)
        horiz = abs(math.cos(ang))
        frond(ic, cx, cy, ang, L, 0.35 + 0.55 * horiz, size * 0.2, tone)
    # dates hanging under the crown
    lay, d = layer()
    for dx in (-18, 14):
        for _ in range(7):
            x, y = cx + dx + R.uniform(-8, 8), cy + 12 + R.uniform(0, 22)
            r = R.uniform(4, 5.5)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(126, 70, 32, 255))
            d.ellipse((x - r * 0.6, y - r * 0.7, x, y - r * 0.1), fill=(196, 130, 70, 180))
    ic.image.alpha_composite(lay)
    ic.shade(ic.mask("ellipse", (cx - 30, cy - 20, cx + 30, cy + 16)), (230, 240, 170), 0.18, blur=8)


def windlass(ic: Icon, cx: float, cy: float) -> None:
    """Well-diggers' windlass: two stout forked posts, a heavy drum with crank, rope and bucket."""
    ic.shade(ic.mask("ellipse", (cx - 80, cy - 10, cx + 140, cy + 34)), (60, 36, 14), 0.3, blur=10)
    lx, rx, top = cx - 74, cx + 74, cy - 190
    timber(ic, (lx, cy + 6), (lx + 6, top), 32)
    timber(ic, (rx, cy + 6), (rx - 6, top), 32)
    for x, s in ((lx + 6, -1), (rx - 6, 1)):  # forks
        timber(ic, (x, top + 8), (x + s * 20, top - 26), 14)
    drum = [(lx - 8, top - 14), (rx + 8, top - 14), (rx + 8, top + 22), (lx - 8, top + 22)]
    dm = ic.poly_mask(drum)
    ic.fill(dm, "#c09868", "#5a3e26", (top - 14, top + 22), noise=0.2)
    ic.shade(ic.intersect(dm, ic.mask("rectangle", (0, top + 6, SIZE, SIZE))), (30, 18, 8), 0.3)
    for x in np.arange(lx + 12, rx - 2, 16):
        ic.line([(x, top - 12), (x + 6, top + 20)], 4, (120, 90, 56, 160))
    ic.line([(lx - 6, top - 10), (rx + 6, top - 10)], 5, (255, 232, 186, 110))
    ic.outline(drum, 4, (40, 26, 16, 190))
    timber(ic, (rx + 8, top + 4), (rx + 40, top + 2), 10)
    timber(ic, (rx + 40, top + 2), (rx + 42, top + 42), 10)
    ic.line([(cx + 6, top + 22), (cx + 8, cy - 46)], 5, (86, 66, 42))
    bucket = [(cx - 16, cy - 48), (cx + 30, cy - 48), (cx + 24, cy - 12), (cx - 10, cy - 12)]
    ic.poly(bucket, "#9a6e46", "#4a3220", edge=4)


def green_bed(ic: Icon, box, rows: int) -> None:
    """Lush garden bed: dark damp soil with rows of leafy green clumps, lit on top."""
    R = ic.random
    x0, y0, x1, y1 = box
    ic.fill(ic.mask("rectangle", box), "#5e4630", "#3e2e1c", (y0, y1), noise=0.3)
    for i in range(rows):
        t = (i + 0.7) / rows
        y = y0 + (y1 - y0) * t
        s = 0.8 + 0.3 * t
        m = Image.new("L", (SIZE, SIZE), 0)
        x = x0 + 12
        while x < x1 - 10:
            m = union(m, ic.poly_mask(ic.jitter(x, y - 8 * s, 13 * s, 10 * s, 9, 0.25)))
            x += R.uniform(15, 21) * s
        ic.fill(m, "#9cc656", "#34521e", (y - 20 * s, y + 6), noise=0.26, chroma=0.12)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 0, SIZE, y - 12 * s))), (230, 244, 160), 0.22, blur=3)


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["gamma"] = 0.9
    ic.grade["mute"] = 0.82

    # ---- garden ground (lower, right) and its shallow cut face
    gtop = [(GX0 + 20, GB), (GX1 - 20, GB), (GX1, GF), (GX0, GF)]
    strata(ic, [(GX0, GF), (GX1, GF), (GX1 - 2, BOT), (GX0, BOT)], GF, BOT)
    gm = ic.poly_mask(gtop)
    ic.fill(gm, "#8a7a4c", "#66583a", (GB, GF), noise=0.3)
    ic.shade(ic.intersect(gm, ic.mask("rectangle", (0, GB, SIZE, GB + 40))), (40, 60, 20), 0.35, blur=12)

    # low fruit bushes along the back of the garden
    for bx, br in ((640, 36), (800, 40), (986 - 40, 40)):
        by = GB + 10
        m = Image.new("L", (SIZE, SIZE), 0)
        for _ in range(6):
            x, y = bx + R.uniform(-br * 0.6, br * 0.6), by - br * 0.6 + R.uniform(-br * 0.3, br * 0.3)
            r = br * R.uniform(0.45, 0.65)
            m = union(m, ic.poly_mask(ic.jitter(x, y, r, r * 0.85, 12, 0.1)))
        ic.shade(ic.mask("ellipse", (bx - br, by - 10, bx + br * 1.4, by + 14)), (30, 20, 8), 0.4, blur=8)
        ic.fill(m, "#7aa04a", "#26401c", radial=(bx - br * 0.7, by - br * 1.2, br * 2.2), noise=0.3, chroma=0.14)
        lay, d = layer()
        for _ in range(5):
            x, y = bx + R.uniform(-br * 0.7, br * 0.7), by - br * R.uniform(0.2, 0.9)
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(176, 52, 36, 255))
            d.ellipse((x - 4, y - 4, x, y), fill=(230, 120, 90, 200))
        composite(ic, lay, m)

    # beds either side of the channel and pool
    green_bed(ic, (GX0 + 26, GB + 40, 736, GF - 50), 4)
    green_bed(ic, (866, GB + 36, GX1 - 22, GF - 12), 5)

    # open channel from the gallery mouth to a pool in the garden
    chan = ic.poly_mask([(GX0 - 4, GF - 38), (760, GF - 46), (778, GF - 28), (GX0 - 4, GF - 8)])
    pool_box = (732, GB + 58, 862, GF - 8)
    pool = union(chan, ic.poly_mask(ic.jitter((pool_box[0] + pool_box[2]) / 2, (pool_box[1] + pool_box[3]) / 2,
                                              (pool_box[2] - pool_box[0]) / 2, (pool_box[3] - pool_box[1]) / 2, 16, 0.05)))
    ic.fill(pool.filter(ImageFilter.MaxFilter(13)), "#b4a07a", "#7a6446", noise=0.25)   # stone / mud kerb
    ic.fill(pool, W_LIGHT, W_DEEP, (GB, GF + 60), noise=0.08, chroma=0.06)
    ic.shade(ic.intersect(pool, ic.mask("rectangle", (0, 0, SIZE, GB + 84))), (20, 44, 50), 0.35, blur=6)
    lay, d = layer()
    for _ in range(12):
        x, y = R.uniform(GX0, 840), R.uniform(GB + 90, GF - 16)
        d.line([(x, y), (x + R.uniform(18, 40), y)], fill=(236, 250, 250, 170), width=4)
    composite(ic, lay, pool)
    ic.shade(ic.intersect(pool, ic.mask("ellipse", (750, GB + 86, 840, GB + 116))), (240, 252, 250), 0.5, blur=6)

    palm(ic, (930, GB + 50), (912, 150), lean=-28, size=172)
    palm(ic, (716, GB + 30), (722, 262), lean=18, size=140)

    # ---- desert plateau: top, then the shallow cut face with shafts and gallery
    ptop = [(PX0 + 70 + (PX1 - 60 - PX0 - 70) * t, PB - 10 * math.sin(math.pi * t * 2.3) ** 2 + R.uniform(-2, 2))
            for t in np.linspace(0, 1, 24)] + [(PX1 + 10, PF - 30), (PX1, PF), (PX0, PF), (PX0 + 10, PB + 60)]
    pm = ic.poly_mask(ptop)
    ic.fill(pm, SAND, SAND_DK, (PB - 20, PF + 40), noise=0.24, chroma=0.12)
    sand_ripples(ic, pm, (PX0, PB, PX1, PF), 26)
    ic.shade(ic.intersect(pm, ic.mask("rectangle", (0, 0, 260, SIZE))), (255, 240, 200), 0.14, blur=40)
    ic.shade(ic.intersect(pm, ic.mask("rectangle", (PX1 - 90, 0, SIZE, SIZE))), (90, 56, 22), 0.2, blur=30)
    face = [(PX0, PF), (PX1, PF), (PX1, BOT), (PX0, BOT)]
    fm = strata(ic, face, PF, BOT)
    # damp aquifer on the left feeding the gallery
    ic.shade(ic.intersect(fm, ic.poly_mask([(PX0, 680), (300, 700), (320, BOT), (PX0, BOT)])), (40, 70, 70), 0.3, blur=24)
    # gallery: dark tunnel with bright water on its floor, out into the garden channel
    hgt = 40
    x0g = GAL0[0] - 24
    gal = [(x0g, gal_y(x0g) - hgt), (GAL1[0], GAL1[1] - hgt), (GAL1[0], GAL1[1] + 4), (x0g, gal_y(x0g) + 4)]
    ic.fill(ic.poly_mask(gal), "#2e2218", "#171009", noise=0.06)
    water = [(x0g, gal_y(x0g) - 20), (GAL1[0] + 2, GAL1[1] - 22), (GAL1[0] + 2, GAL1[1] + 4), (x0g, gal_y(x0g) + 4)]
    ic.fill(ic.poly_mask(water), "#8ccad4", W_DEEP, (GAL0[1] - 24, GAL1[1] + 16), noise=0.08)
    ic.line([(x0g, gal_y(x0g) - 19), (GAL1[0], GAL1[1] - 21)], 4, (236, 250, 250, 210))
    # shafts from each mound position down to the gallery, with footholds
    for x, _, s in MOUNDS:
        yb = gal_y(x) - hgt + 4
        w = 10 + 6 * s
        ic.fill(ic.poly_mask([(x - w, PF), (x + w, PF), (x + w, yb), (x - w, yb)]), "#2e2218", "#1a120c", noise=0.06)
        ic.line([(x - w, PF), (x - w, yb)], 4, (240, 214, 160, 110))
        for y in np.arange(PF + 16, yb - 6, 22):
            ic.line([(x - w + 5, y), (x - 1, y + 4)], 3, (130, 96, 62, 160))
        ic.shade(ic.mask("rectangle", (x + w, PF, x + w + 14, yb)), (40, 22, 8), 0.25, blur=4)

    # ---- mounds on the sand (back to front along the diagonal, mother well largest)
    for x, y, s in MOUNDS:
        mound(ic, x, y, s)
    windlass(ic, MOUNDS[0][0], MOUNDS[0][1] - 18)
