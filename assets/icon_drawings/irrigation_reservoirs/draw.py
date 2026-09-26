"""Irrigation Reservoirs (irrigation_reservoirs): an earthen dam holding a tank, a stone outlet with its sluice.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/irrigation_reservoirs/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/irrigation_reservoirs

Identity: a broad grassed earth embankment seen front-on, the stored water of the tank showing
over its crest. In the middle a dressed-stone outlet headwall runs down the dam face with a timber
sluice frame and windlass on the crest; at its foot water gushes from an arched culvert into a
stone-lined feeder channel that runs forward between two small green fields. Stone steps climb
the dam on the left, a tree and reeds stand on the far shore. Unlike vanilla khmer_baray (carved
faces) and oma_falaj (pipe between piers), the embankment and the water held behind it dominate.

Family (irrigation): shares earth, water and timber palette with irrigated_fields, qanats and
jiangnan_hill_terraces.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 17
REFS = ("khmer_baray", "oma_falaj", "irrigation_systems", "polders")

EARTH, EARTH_DK = "#8e7250", "#54402a"
BUND, BUND_DK = "#a88a5e", "#6e5638"
W_LIGHT, W_DEEP = "#7cc0cc", "#2a6070"
WOOD, WOOD_DK = "#86603e", "#4e3522"
STONE, STONE_DK = "#b09c80", "#6e5e4c"
GRASS, GRASS_DK = "#8a9650", "#4e5a2a"

# ---- layout (1024 canvas) -----------------------------------------------------------------------
FAR = 334            # far water line (the far bank is a thin strip above it)
CREST = 482          # dam crest (top of the near slope), straight
CREST_W = 28         # crest path depth
FLAT0, FLAT1 = 318, 706  # straight stretch of the far shore; the tank ends are shallow quarter ellipses
TOE = 736            # foot of the dam slope
FIELD = 846          # front edge of the fields
FACE = 44            # earth face below the fields
DX0, DX1 = 96, 928   # crest ends
TX0, TX1 = 22, 1002  # toe ends
HX0, HX1 = 430, 594  # outlet headwall


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


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(30, 44), width=(50, 110), moss=True) -> Image.Image:
    """Weathered ashlar face: per-block tint, soft bevels, grime streaks, damp mossy foot."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, base, dark, (x0 - 120, x1 + 120), vertical=False, noise=0.22, chroma=0.14)
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
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
            x = xb
        y = yb
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 45)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.25, 0.7) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 12), y0, sx + R.uniform(5, 12), y0 + ln))),
                 (35, 30, 22), R.uniform(0.10, 0.2), blur=6)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - 90, x1, y1 + 40))), (22, 30, 20), 0.4, blur=22)
    if moss:
        for _ in range(int((x1 - x0) / 30)):
            mx, my = R.uniform(x0, x1), y1 - R.uniform(8, 70)
            blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(12, 28), R.uniform(7, 14), 8, 0.3)))
            ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)
    return m


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float, light="#7a8c4c", dark="#2f3f1e", n: int = 16) -> Image.Image:
    """Tree crown as one massed shape with lit clumps upper left and dark pockets lower right."""
    R = ic.random
    m = Image.new("L", (SIZE, SIZE), 0)
    lumps = []
    for _ in range(n):
        a = R.uniform(0, 2 * math.pi)
        dd = R.uniform(0.0, 0.6) ** 0.8
        bx, by = cx + math.cos(a) * rx * dd, cy + math.sin(a) * ry * dd
        br = min(rx, ry) * R.uniform(0.45, 0.62)
        lumps.append((bx, by, br))
        m = union(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.85, 14, 0.07)))
    ic.fill(m, light, dark, radial=(cx - rx * 0.6, cy - ry * 0.7, max(rx, ry) * 2.0), noise=0.3, chroma=0.16)
    for bx, by, br in lumps:
        cap = ic.poly_mask(ic.jitter(bx - br * 0.25, by - br * 0.3, br * 0.6, br * 0.45, 8, 0.25))
        ic.shade(ic.intersect(cap, m), (220, 235, 150), 0.16, blur=3)
        under = ic.poly_mask(ic.jitter(bx + br * 0.2, by + br * 0.45, br * 0.8, br * 0.35, 8, 0.25))
        ic.shade(ic.intersect(under, m), (8, 18, 6), 0.3, blur=5)
    return m


def tufts(ic: Icon, clip: Image.Image, box, n: int, hmin=10, hmax=26) -> None:
    """Grass blades scattered over a slope (inside ``clip``)."""
    R = ic.random
    x0, y0, x1, y1 = box
    lay, d = layer()
    for _ in range(n):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        for _ in range(R.randint(3, 6)):
            h = R.uniform(hmin, hmax)
            col = (R.randint(96, 140), R.randint(118, 150), R.randint(52, 72), 220)
            d.line([(x, y), (x + R.uniform(-10, 10), y - h)], fill=col, width=4)
    composite(ic, lay, clip)


def earth_face(ic: Icon, top_pts, depth: float) -> Image.Image:
    """Cut earth face below a top edge: strata, clods and pebbles, darker foot."""
    R = ic.random
    bottom = [(x, y + depth) for x, y in top_pts[::-1]]
    pts = list(top_pts) + bottom
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, EARTH, EARTH_DK, (min(ys), max(ys)), noise=0.3, chroma=0.14)
    lay, d = layer()
    for k in range(3):
        f = (k + 0.7) / 3.6
        d.line([(x, y + depth * f + R.uniform(-3, 3)) for x, y in top_pts], fill=(40, 28, 16, 60), width=R.randint(3, 5))
    for _ in range(int((max(xs) - min(xs)) / 9)):
        x = R.uniform(min(xs), max(xs))
        y = top_pts[0][1] + R.uniform(6, depth - 4)
        r = R.uniform(4, 10)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 20, 12, 110))
        d.ellipse((x - r * 0.9, y - r * 0.8, x + r * 0.5, y + r * 0.3), fill=(214, 186, 140, 90))
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, top_pts[0][1] + depth * 0.5, SIZE, SIZE))), (20, 14, 8), 0.3, blur=10)
    return m


def sprouts(ic: Icon, box, rows: int, dark=False) -> None:
    """Small green field: dark damp soil with drill rows of young crop, smaller to the back."""
    x0, y0, x1, y1 = box
    ic.fill(ic.mask("rectangle", box), "#5e4630", "#3e2e1c", (y0, y1), noise=0.32)
    R = ic.random
    lay, d = layer()
    for i in range(rows):
        t = (i + 0.6) / rows
        y = y0 + (y1 - y0) * t
        s = 0.75 + 0.3 * t
        d.line([(x0 + 6, y + 4), (x1 - 6, y + 4)], fill=(30, 22, 12, 130), width=int(8 * s))
        x = x0 + 10
        while x < x1 - 8:
            for _ in range(4):
                h = R.uniform(16, 30) * s
                col = (R.randint(90, 130), R.randint(130, 162), R.randint(48, 70), 240)
                d.line([(x, y), (x + R.uniform(-8, 8) * s, y - h)], fill=col, width=max(3, int(4 * s)))
            x += 20 * s
    composite(ic, lay)


# ---- parts ---------------------------------------------------------------------------------------
def arch(cx: float, base: float, rx: float, ry: float, p: float = 2.6, n: int = 40, jit=None):
    """Upper half of a superellipse (rounded box seen from the raised camera), left to right."""
    out = []
    for a in np.linspace(math.pi, 2 * math.pi, n):
        c, s = math.cos(a), math.sin(a)
        x = cx + rx * math.copysign(abs(c) ** (2 / p), c)
        y = base + ry * math.copysign(abs(s) ** (2 / p), s)
        if jit:
            y += jit.uniform(-5, 3)
        out.append((x, y))
    return out


def side(p0, p1, bulge: float, n: int = 12):
    """Quadratic curve from p0 to p1 bowed outwards by ``bulge`` (x offset of the control point)."""
    cx, cy = (p0[0] + p1[0]) / 2 + bulge, (p0[1] + p1[1]) / 2 - abs(bulge) * 0.6
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t * t * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t * t * p1[1]) for t in np.linspace(0, 1, n)]


def tank(far_y: float, base_y: float, x0: float, x1: float, f0: float, f1: float, n: int = 14, jit=None):
    """Flat sheet outline: shallow quarter-ellipse ends from the crest corners up to a straight far shore."""
    ry = base_y - far_y
    pts = []
    for a in np.linspace(math.pi, 1.5 * math.pi, n):
        pts.append((f0 + (f0 - x0) * math.cos(a), base_y + ry * math.sin(a)))
    for x in np.linspace(f0, f1, 10)[1:-1]:
        pts.append((x, far_y + (jit.uniform(-3, 3) if jit else 0)))
    for a in np.linspace(1.5 * math.pi, 2 * math.pi, n):
        pts.append((f1 + (x1 - f1) * math.cos(a), base_y + ry * math.sin(a)))
    return pts


def far_shore(ic: Icon) -> None:
    """Thin grassed far bank round the tank, wider at the dam ends; low reeds on the water line."""
    R = ic.random
    bank = tank(FAR - 24, CREST + 2, DX0 - 14, DX1 + 14, FLAT0 - 16, FLAT1 + 16, jit=R)
    m = ic.poly_mask(bank)
    ic.fill(m, "#94a05a", "#5a6232", (FAR - 30, CREST), noise=0.3, chroma=0.14)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 0, 420, SIZE))), (255, 240, 200), 0.14, blur=20)
    lay, d = layer()
    for x in list(np.linspace(190, 360, 18)) + list(np.linspace(610, 700, 9)):
        h = R.uniform(16, 30)
        col = (R.randint(104, 140), R.randint(116, 140), R.randint(56, 72), 230)
        d.line([(x, FAR + 6), (x + R.uniform(-6, 6), FAR + 6 - h)], fill=col, width=5)
    composite(ic, lay)


def shore_tree(ic: Icon) -> None:
    """Broad tree rooted on the right end of the bank, its crown overlapping bank and water."""
    tx, ty = 900, CREST - 6
    ic.shade(ic.mask("ellipse", (tx - 70, ty - 14, tx + 50, ty + 14)), alpha=0.45, blur=8)
    timber(ic, (tx, ty), (tx - 10, ty - 110), 22, "#6e5640", "#3a2a1c")
    timber(ic, (tx - 6, ty - 70), (tx - 44, ty - 118), 11, "#6e5640", "#3a2a1c")
    canopy(ic, tx - 24, ty - 150, 112, 70, n=20)


def reservoir(ic: Icon) -> Image.Image:
    """Stored water between the far shore and the crest: lighter far sheen, highlight streak, ripples."""
    pts = tank(FAR, CREST + 4, DX0 + 28, DX1 - 28, FLAT0, FLAT1)
    m = ic.poly_mask(pts)
    ic.fill(m, W_LIGHT, W_DEEP, (FAR - 70, CREST + 30), noise=0.08, chroma=0.06)
    # the bank's dark reflection along the far edge
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, FAR - 10, SIZE, FAR + 22))), (30, 50, 40), 0.35, blur=8)
    # broad sky highlight streak across the sheet
    streak = ic.poly_mask([(150, FAR + 70), (790, FAR + 60), (750, FAR + 98), (180, FAR + 108)])
    ic.shade(ic.intersect(m, streak), (226, 246, 246), 0.6, blur=12)
    core = ic.poly_mask([(220, FAR + 80), (680, FAR + 74), (650, FAR + 90), (250, FAR + 94)])
    ic.shade(ic.intersect(m, core), (245, 252, 250), 0.7, blur=5)
    R = ic.random
    lay, d = layer()
    for _ in range(26):
        y = R.uniform(FAR + 26, CREST - 8)
        x = R.uniform(DX0 + 40, DX1 - 120)
        L = R.uniform(30, 90)
        d.line([(x, y), (x + L, y)], fill=(226, 242, 244, R.randint(100, 170)), width=4)
        d.line([(x + 10, y + 7), (x + L - 6, y + 7)], fill=(20, 45, 58, 80), width=3)
    composite(ic, lay, m)
    # darker water against the dam
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, CREST - 30, SIZE, SIZE))), (16, 40, 50), 0.3, blur=10)
    # tree reflection
    ic.shade(ic.intersect(m, ic.mask("ellipse", (780, FAR + 30, 930, CREST + 20))), (30, 56, 30), 0.35, blur=12)
    return m


def dam(ic: Icon) -> Image.Image:
    """Crest path and the grassed near slope, darker and wetter towards the toe."""
    R = ic.random
    crest = [(DX0 - 12, CREST), (DX1 + 12, CREST), (DX1 + 18, CREST + CREST_W), (DX0 - 18, CREST + CREST_W)]
    ic.poly(crest, "#b89c70", "#8e7450", noise=0.3, edge=0)
    slope = side((TX0, TOE), (DX0 - 18, CREST + CREST_W), 8) + side((DX1 + 18, CREST + CREST_W), (TX1, TOE), -8)
    m = ic.poly_mask(slope)
    # light at the crest, darkening steadily down the face to a damp toe
    ic.fill(m, "#a8b068", "#454a26", (CREST + CREST_W, TOE + 30), noise=0.2, chroma=0.16)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 0, 300, SIZE))), (255, 240, 200), 0.10, blur=60)
    # bare earth patches and erosion streaks down the face
    for _ in range(8):
        x, y = R.uniform(TX0 + 60, TX1 - 60), R.uniform(CREST + 70, TOE - 40)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(x, y, R.uniform(18, 40), R.uniform(10, 18), 9, 0.3))),
                 (140, 108, 70), 0.4, blur=6)
    for _ in range(12):
        x = R.uniform(TX0 + 60, TX1 - 60)
        ic.shade(ic.intersect(m, ic.poly_mask([(x, CREST + 40), (x + 10, CREST + 40), (x + 26, TOE), (x - 8, TOE)])),
                 (50, 44, 22), 0.2, blur=8)
    tufts(ic, m, (TX0, CREST + 40, TX1, TOE), 70, 6, 14)
    # darker grass tufts as soft clumps, denser low down
    for _ in range(34):
        x, y = R.uniform(TX0 + 30, TX1 - 30), CREST + 70 + (TOE - CREST - 70) * R.random() ** 0.6
        clump = ic.poly_mask(ic.jitter(x, y - 6, R.uniform(14, 26), R.uniform(7, 11), 9, 0.35))
        ic.shade(ic.intersect(m, clump), (34, 50, 20), R.uniform(0.45, 0.65), blur=3)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(x - 5, y - 11, 10, 4, 7, 0.3))), (190, 205, 120), 0.25, blur=2)
    # wet seepage streaks either side of the outlet
    for _ in range(12):
        x = R.choice([R.uniform(HX0 - 150, HX0 - 30), R.uniform(HX1 + 30, HX1 + 150)])
        y0 = R.uniform(TOE - 230, TOE - 130)
        ic.shade(ic.intersect(m, ic.poly_mask([(x, y0), (x + 10, y0), (x + 20, TOE), (x - 10, TOE)])),
                 (16, 42, 44), R.uniform(0.35, 0.5), blur=5)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (HX0 - 200, TOE - 70, HX1 + 200, TOE + 60))), (14, 34, 30), 0.35, blur=20)
    # stone pitching along the toe of the slope
    for x in np.arange(TX0 + 14, TX1 - 10, 30):
        if HX0 - 80 < x < HX1 + 80:
            continue
        r = R.uniform(15, 21)
        y = TOE - R.uniform(8, 16)
        ic.fill(ic.poly_mask(ic.jitter(x, y, r, r * 0.7, 8, 0.15)), "#b4a488", "#6e604e",
                radial=(x - r * 0.6, y - r * 0.6, r * 2), noise=0.2)
    # the slope darkens and gets damp at the toe; left end lit, right end in shade
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, TOE - 80, SIZE, TOE + 20))), (20, 26, 10), 0.3, blur=24)
    ic.shade(ic.intersect(m, ic.poly_mask([(DX1 - 40, CREST), (SIZE, CREST), (SIZE, TOE), (TX1 - 110, TOE)])), alpha=0.22,
             blur=30)
    ic.line([(DX0 - 18, CREST + CREST_W), (DX1 + 18, CREST + CREST_W)], 4, (60, 50, 30, 150))
    ic.line([(DX0 - 12, CREST + 3), (DX1 + 12, CREST + 3)], 5, (236, 222, 184, 150))
    return m


def steps(ic: Icon) -> None:
    """Stone steps up the dam face, left of the outlet."""
    n = 9
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        y0 = CREST + CREST_W + (TOE - CREST - CREST_W) * t0
        y1 = CREST + CREST_W + (TOE - CREST - CREST_W) * t1
        xc = 320 - 70 * t0
        w = 70 + 16 * t0
        tread = [(xc - w / 2, y0), (xc + w / 2, y0), (xc + w / 2 - 4, y0 + (y1 - y0) * 0.45), (xc - w / 2 - 4, y0 + (y1 - y0) * 0.45)]
        ic.poly(tread, "#c6b494", "#a8967a", edge=3)
        riser = [tread[3], tread[2], (xc + w / 2 - 8, y1), (xc - w / 2 - 8, y1)]
        ic.poly(riser, "#8a7a64", "#62564a", edge=3)


def outlet(ic: Icon) -> None:
    """Stone headwall down the dam face, culvert arch at its foot with gushing water, sluice frame on top."""
    top = CREST - 14
    # side wing walls follow the slope
    for side in (-1, 1):
        x = HX0 if side < 0 else HX1
        wing = [(x, top + 30), (x + side * 26, top + 40), (x + side * 70, TOE), (x, TOE)]
        ic.poly(wing, "#a08c72", "#6a5a48", noise=0.25, edge=4)
    face = ashlar(ic, (HX0, top, HX1, TOE))
    ic.shade(ic.intersect(face, ic.mask("rectangle", (HX0 + (HX1 - HX0) * 0.6, 0, SIZE, SIZE))), alpha=0.28, blur=12)
    ic.line([(HX0 + 3, top), (HX0 + 3, TOE)], 5, (255, 244, 222, 90))
    # coping
    ic.rect((HX0 - 14, top - 18, HX1 + 14, top + 4), "#cab89a", "#9a886e", edge=4)
    ic.shade(ic.mask("rectangle", (HX0, top + 4, HX1, top + 22)), alpha=0.4, blur=6)
    # culvert arch at the foot
    ax0, ax1, ay = HX0 + 34, HX1 - 34, TOE - 110
    mx = (ax0 + ax1) / 2
    ic.fill(ic.mask("ellipse", (ax0 - 18, ay - 18, ax1 + 18, ay + (ax1 - ax0) + 18)), "#c4b294", "#8e7c62", noise=0.2)
    ic.fill(ic.mask("rectangle", (ax0 - 18, ay + (ax1 - ax0) / 2, ax1 + 18, TOE)), "#c4b294", "#8e7c62", noise=0.2)
    for a in range(190, 355, 24):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        r0, r1 = (ax1 - ax0) / 2, (ax1 - ax0) / 2 + 18
        cy = ay + (ax1 - ax0) / 2
        ic.line([(mx + r0 * ca, cy + r0 * sa), (mx + r1 * ca, cy + r1 * sa)], 3, (50, 40, 30, 160))
    hole = union(ic.mask("ellipse", (ax0, ay, ax1, ay + (ax1 - ax0))), ic.mask("rectangle", (ax0, ay + (ax1 - ax0) / 2, ax1, TOE)))
    ic.fill(hole, "#231e19", "#141110", noise=0.05)
    # water gushing out of the culvert
    lay, d = layer()
    d.polygon([(ax0 + 2, TOE - 44), (ax1 - 2, TOE - 44), (ax1 + 20, TOE + 30), (ax0 - 20, TOE + 30)], fill=(200, 232, 236, 240))
    for x in np.arange(ax0 + 6, ax1, 11):
        d.line([(x, TOE - 40), (x + (x - mx) * 0.4, TOE + 28)], fill=(255, 255, 255, 190), width=5)
    ic.image.alpha_composite(lay)
    # sluice frame and windlass on the crest over the gate shaft
    fx0, fx1, ft = HX0 + 22, HX1 - 22, top - 190
    ic.shade(ic.poly_mask([(fx1, top - 20), (fx1 + 70, top - 20), (fx1 + 80, top + 30), (fx1, top + 30)]), alpha=0.3, blur=12)
    timber(ic, (fx0, top - 10), (fx0 + 4, ft), 36)
    timber(ic, (fx1, top - 10), (fx1 - 4, ft), 36)
    timber(ic, (fx0 - 30, ft + 6), (fx1 + 30, ft + 2), 32)
    timber(ic, (fx0 + 8, top - 70), (fx1 - 8, top - 72), 20)
    # gate leaf raised in its guides
    ic.rect((fx0 + 26, top - 120, fx1 - 26, top - 20), "#94683f", "#5a3e26", vertical=False, edge=4)
    for y in (top - 94, top - 50):
        ic.line([(fx0 + 22, y), (fx1 - 22, y)], 6, (60, 58, 56))
    # windlass drum with handle on the crossbeam
    ic.ellipse((fx0 + 34, ft - 34, fx1 - 34, ft + 2), "#9a7652", "#5a3e26", edge=4)
    ic.line([(mx, ft + 2), (mx, top - 120)], 5, (60, 50, 36))
    timber(ic, (fx1 + 12, ft - 16), (fx1 + 40, ft - 30), 9)


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.84

    far_shore(ic)
    reservoir(ic)
    shore_tree(ic)
    slope = dam(ic)
    steps(ic)

    # front: small fields either side of the feeder channel, earth face below
    front = [(TX0 + 10 + (TX1 - TX0 - 20) * t, FIELD + R.uniform(-3, 3)) for t in np.linspace(0, 1, 20)]
    earth_face(ic, front, FACE)
    ic.fill(ic.mask("rectangle", (TX0 + 10, TOE, TX1 - 10, FIELD + 8)), "#8a6e48", "#6c5234", (TOE, FIELD), noise=0.3)
    cx0, cx1 = HX0 + 14, HX1 - 14
    sprouts(ic, (TX0 + 40, TOE + 22, cx0 - 44, FIELD - 12), 4)
    sprouts(ic, (cx1 + 44, TOE + 22, TX1 - 40, FIELD - 12), 4)
    for x0, x1 in ((TX0 + 30, cx0 - 34), (cx1 + 34, TX1 - 30)):  # bunds round the fields
        ic.line([(x0, TOE + 14), (x1, TOE + 14)], 12, (168, 138, 94))
        ic.line([(x0, FIELD - 6), (x1, FIELD - 6)], 12, (168, 138, 94))
    # stone-lined feeder channel towards the viewer
    ic.fill(ic.mask("rectangle", (cx0 - 26, TOE, cx1 + 26, FIELD + FACE)), "#b4a286", "#7e6c56", noise=0.25)
    ch = ic.mask("rectangle", (cx0, TOE, cx1, FIELD + FACE - 6))
    ic.fill(ch, W_LIGHT, W_DEEP, (TOE - 200, FIELD + 200), noise=0.08)
    lay, d = layer()
    for _ in range(26):
        x, y = R.uniform(cx0, cx1 - 20), R.uniform(TOE + 20, FIELD + FACE - 10)
        d.line([(x, y), (x + R.uniform(16, 40), y)], fill=(236, 248, 248, R.randint(130, 200)), width=4)
    composite(ic, lay, ch)
    ic.shade(ic.intersect(ch, ic.mask("rectangle", (cx0, 0, cx0 + 22, SIZE))), alpha=0.35, blur=6)
    for x in (cx0 - 26, cx1 + 26):
        ic.line([(x, TOE), (x, FIELD + FACE)], 4, (60, 48, 36, 170))

    outlet(ic)

    # a spade stuck in the bund, bottom left
    timber(ic, (140, FIELD - 20), (176, FIELD - 150), 10, "#a07a52", "#5e4228")
    ic.poly([(126, FIELD - 26), (156, FIELD - 18), (150, FIELD + 12), (120, FIELD + 4)], "#7a7670", "#4a4644", edge=4)
    ic.shade(slope, (0, 0, 0), 0.0)
