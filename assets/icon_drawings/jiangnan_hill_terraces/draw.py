"""Jiangnan Hill Terraces (jiangnan_hill_terraces): curved flooded rice terraces stepping up a hill.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/jiangnan_hill_terraces/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/jiangnan_hill_terraces

Identity: five sinuous contour terraces of uneven width (one bulging out, one pinched) stepping up
a scrubby hill, each a pale sky-teal sheet of standing water planted with green rice rows (dense
low down, thinning higher up), held by earth-and-stone walls with grassy lips; soft falls spill
from tier to tier on the left. A white-walled, black-tiled Huizhou farmhouse with tall stepped
horse-head gables crowns the hill in front of a broad camphor tree, a bamboo clump grows on the
lower right flank. Unlike vanilla terraces (three square green steps) the terraces are curved,
flooded and planted in rows.

Family (irrigation): shares earth, water and timber palette with irrigated_fields,
irrigation_reservoirs and qanats.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 31
REFS = ("terraces", "farming_village", "clan_family_shrine", "irrigation_systems")

EARTH, EARTH_DK = "#8a7050", "#4e3e2a"
WOOD, WOOD_DK = "#86603e", "#4e3522"

# ---- terrace geometry --------------------------------------------------------------------------
CX = 512
TIERS = 5
Y0 = 812          # front edge of the lowest terrace (centre)
D = 62            # depth of a terrace surface
H = 50            # height of a retaining wall
# per tier: half width, centre offset, forward bulge, contour wobble (amplitude, phase)
HALF = (492, 424, 386, 262, 206)
OFF = (0, -10, 22, -8, 8)
BULGE = (40, 30, 70, 20, 40)
WOB = ((10, 0.4), (12, 2.1), (9, 4.0), (12, 1.0), (7, 3.1))


def half(i: int) -> float:
    return HALF[i]


def cx(i: int) -> float:
    return CX + OFF[i]


def front_y(i: int, x: float) -> float:
    """Front edge of terrace i at x: bowed towards the viewer, with a slow sinuous wobble."""
    u = (x - cx(i)) / half(i)
    a, ph = WOB[i]
    return Y0 - (D + H) * i + BULGE[i] * (1 - min(1.0, u * u)) + a * math.sin(2.4 * math.pi * u + ph)


def back_y(i: int, x: float) -> float:
    """Back edge of terrace i: the foot of the wall above (or the hilltop for the top tier)."""
    if i == TIERS - 1:
        return front_y(i, x) - D
    return front_y(i + 1, x) + H - 4


def front(i: int, n: int = 44, shrink: float = 0.0):
    h = half(i) - shrink
    return [(x, front_y(i, x)) for x in np.linspace(cx(i) - h, cx(i) + h, n)]


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
    ic.outline(pts, 4, (40, 26, 16, 170))


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


# ---- parts -------------------------------------------------------------------------------------
RICE_ROWS = (4, 4, 3, 2, 2)
RICE_STEP = (13, 15, 20, 26, 30)


def terrace(ic: Icon, i: int) -> None:
    """One terrace: pale reflective water sheet with green rice rows, then its wall with a grassy lip."""
    R = ic.random
    fr = front(i)
    xs = np.linspace(cx(i) - half(i) + 22, cx(i) + half(i) - 22, 44)
    back = [(x, back_y(i, x)) for x in xs][::-1]
    sm = ic.poly_mask(fr + back)
    ys = [p[1] for p in fr + back]
    # flooded paddy: pale sky teal, a touch deeper towards the front, shade under the wall above
    ic.fill(sm, "#d4ebe6", "#8cbcbc", (min(ys), max(ys) + 10), noise=0.07, chroma=0.05)
    ic.shade(ic.intersect(sm, ic.poly_mask([(x, y - 6) for x, y in back[::-1]] + [(x, y + 16) for x, y in back])),
             (40, 70, 60), 0.3, blur=6)
    lay, d = layer()
    for _ in range(10):
        x = R.uniform(cx(i) - half(i) * 0.8, cx(i) + half(i) * 0.8)
        y = (front_y(i, x) + back_y(i, x)) / 2 + R.uniform(-10, 10)
        d.line([(x, y), (x + R.uniform(24, 60), y)], fill=(250, 255, 252, R.randint(120, 190)), width=3)
    composite(ic, lay, sm)
    # rice: rows of green clumps following the contour, dense below, thinning higher up
    rows, step = RICE_ROWS[i], RICE_STEP[i]
    sz = 1.0 if i <= 1 else 0.85 if i == 2 else 0.72
    lay, d = layer()
    for r in range(rows):
        f = (r + 0.75) / (rows + 0.35)
        x = cx(i) - half(i) + 34 + R.uniform(0, 8)
        while x < cx(i) + half(i) - 34:
            u = abs(x - cx(i)) / half(i)
            yb, yf = back_y(i, x), front_y(i, x)
            y = yb + (yf - yb) * f
            if u < 0.93 and yf - yb > 20:
                s = sz * (0.8 + 0.3 * f) * R.uniform(0.85, 1.15)
                rx, ry = 11 * s, 11 * s
                d.line([(x - rx * 0.8, y + 3), (x + rx * 0.8, y + 3)], fill=(50, 80, 70, 70), width=3)   # reflection
                g = R.randint(-10, 18)
                lean = R.uniform(-3, 3)
                fan = [(x - rx * 0.35, y + 2), (x + rx * 0.35, y + 2), (x + rx + lean, y - ry * 1.3),
                       (x + rx * 0.3 + lean, y - ry * 0.9), (x + lean, y - ry * 1.8), (x - rx * 0.3 + lean, y - ry * 0.9),
                       (x - rx + lean, y - ry * 1.3)]
                d.polygon(fan, fill=(62 + g, 112 + g, 34, 255))
                d.polygon([(x - rx * 0.3, y - ry * 0.3), (x - rx * 0.9 + lean, y - ry * 1.25), (x - rx * 0.2 + lean, y - ry * 0.95),
                           (x + lean, y - ry * 1.7), (x + rx * 0.15, y - ry * 0.4)], fill=(136 + g, 186 + g, 72, 230))
            x += step * R.uniform(0.85, 1.15)
    composite(ic, lay, sm)
    # retaining wall below the front edge
    wall = fr + [(x, y + H * (1 - abs((x - cx(i)) / half(i)) ** 6)) for x, y in fr[::-1]]
    wm = ic.poly_mask(wall)
    ic.fill(wm, EARTH, EARTH_DK, (front_y(i, cx(i)) - 10, front_y(i, cx(i)) + H), noise=0.3, chroma=0.14)
    lay, d = layer()
    for k in range(int(half(i) * 2 / 22)):  # rough stones in the lower wall
        x = cx(i) - half(i) + k * 22 + R.uniform(-4, 4)
        y = front_y(i, x) + R.uniform(H * 0.45, H * 0.85)
        r = R.uniform(8, 13)
        d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(150, 136, 112, 150))
        d.arc((x - r, y - r * 0.6, x + r, y + r * 0.6), 0, 180, fill=(40, 30, 20, 140), width=3)
    composite(ic, lay, wm)
    ic.shade(ic.intersect(wm, ic.mask("rectangle", (cx(i) + half(i) * 0.3, 0, SIZE, SIZE))), alpha=0.22, blur=30)
    ic.shade(ic.intersect(wm, ic.poly_mask([(x, y + H * 0.6) for x, y in fr] + [(x, y + H + 4) for x, y in fr[::-1]])),
             (20, 14, 8), 0.3, blur=8)
    # grassy lip of the bund
    ic.line(fr, 13, (104, 136, 58))
    ic.line([(x, y - 3) for x, y in fr], 5, (170, 196, 110, 200))
    lay, d = layer()
    for x, y in fr[1:-1]:
        for _ in range(3):
            xx = x + R.uniform(-12, 12)
            yy = front_y(i, xx)
            d.line([(xx, yy + 4), (xx + R.uniform(-8, 8), yy + R.uniform(10, 22))], fill=(100, 130, 56, 200), width=3)
    composite(ic, lay)


def spill(ic: Icon, i: int, x: float) -> None:
    """Soft pale-teal fall through a notch in the lip of terrace i, down its wall into the tier below."""
    y0 = front_y(i, x) - 10
    y1 = back_y(i - 1, x) + 12
    m = ic.poly_mask([(x - 9, y0), (x + 9, y0), (x + 16, y1), (x - 16, y1)])
    ic.shade(m, (178, 220, 218), 0.95, blur=2)
    ic.shade(ic.poly_mask([(x - 4, y0 + 6), (x + 1, y0 + 6), (x - 1, y1 - 6), (x - 8, y1 - 6)]), (236, 248, 244), 0.5, blur=3)
    ic.shade(ic.mask("ellipse", (x - 26, y1 - 10, x + 26, y1 + 10)), (214, 238, 234), 0.7, blur=4)


def farmhouse(ic: Icon, x0: float, x1: float, foot: float) -> None:
    """Huizhou-style farmhouse: wide white walls, black tile roof, tall stepped horse-head gables."""
    R = ic.random
    eave = foot - 128
    ridge = eave - 78
    w = x1 - x0
    # roof between the gables
    roof = [(x0 + 14, eave + 6), (x1 - 14, eave + 6), (x1 - 34, ridge), (x0 + 34, ridge)]
    ic.poly(roof, "#5a5a5e", "#2c2c30", edge=0)
    lay, d = layer()
    for x in np.arange(x0 + 20, x1 - 20, 12):
        d.line([(x, ridge + 2), (x, eave + 4)], fill=(20, 20, 24, 130), width=3)
        d.line([(x + 4, ridge + 2), (x + 4, eave + 4)], fill=(160, 160, 166, 70), width=2)
    composite(ic, lay, ic.poly_mask(roof))
    ic.line([(x0 + 30, ridge), (x1 - 30, ridge)], 14, (38, 38, 42))
    # white walls
    wall = ic.mask("rectangle", (x0, eave + 6, x1, foot))
    ic.fill(wall, "#f2eee2", "#c2bba8", (x0, x1), vertical=False, noise=0.12)
    ic.shade(ic.intersect(wall, ic.mask("rectangle", (x0, eave + 6, x1, eave + 34))), alpha=0.4, blur=8)
    ic.shade(ic.intersect(wall, ic.mask("rectangle", (x0, foot - 30, x1, foot))), (60, 70, 50), 0.35, blur=8)
    for _ in range(6):  # damp streaks on the lime wash
        sx = R.uniform(x0 + 10, x1 - 10)
        ic.shade(ic.intersect(wall, ic.mask("rectangle", (sx - 6, eave + 20, sx + 6, eave + R.uniform(60, 100)))), (80, 80, 70),
                 0.12, blur=5)
    # tall stepped horse-head gables at both ends, clearly rising above the roof in two steps
    for gx, s in ((x0, 1), (x1, -1)):
        a0, a, b = w * 0.07, w * 0.15, w * 0.24
        hi0, hi1, hi2 = ridge + 26, ridge - 16, ridge - 58
        steps = [(0, eave + 6), (0, hi0), (a0, hi0), (a0, hi1), (a, hi1), (a, hi2), (b, hi2), (b, eave + 6)]
        pts = [(gx + s * dx, y) for dx, y in steps]
        gm = ic.poly_mask(pts)
        ic.fill(gm, "#f6f2e6", "#c6bea8", (hi2, eave), noise=0.1)
        ic.shade(ic.intersect(gm, ic.mask("rectangle", (min(gx, gx + s * a), 0, max(gx, gx + s * a), SIZE))), alpha=0.16)
        ic.shade(ic.intersect(gm, ic.mask("rectangle", (0, ridge - 6, SIZE, eave + 6))), alpha=0.12, blur=6)
        for lo, hi, y in ((-8, a0 + 6, hi0 - 8), (a0 - 6, a + 6, hi1 - 8), (a - 6, b + 8, hi2 - 8)):
            cap = [(gx + s * lo, y), (gx + s * hi, y), (gx + s * hi, y + 18), (gx + s * lo, y + 18)]
            ic.poly(cap, "#48484c", "#1e1e22", edge=3)
        ic.line([(gx + s * (b + 6), hi2 - 8), (gx + s * (b + 18), hi2 - 22)], 10, (36, 36, 40))
    # door and small dark windows
    dx0 = x0 + w * 0.43
    ic.rect((dx0, foot - 72, dx0 + 48, foot), "#4a3424", "#2a1c12", edge=4)
    ic.fill(ic.mask("rectangle", (dx0 - 12, foot - 86, dx0 + 60, foot - 74)), "#56565a", "#34343a", noise=0.1)
    for wx, wy in ((x0 + w * 0.13, eave + 30), (x1 - w * 0.2, eave + 44)):
        ic.rect((wx, wy, wx + 18, wy + 30), "#2e2c2c", "#1a1818", edge=3)


def bamboo(ic: Icon, x0: float, base: float, n: int = 4, h: float = 220) -> None:
    """Clump of bamboo: a few light green jointed culms leaning out, massed leaf sprays."""
    R = ic.random
    culms = []
    for k in range(n):
        x = x0 + (k - n / 2) * 16 + R.uniform(-5, 5)
        top = (x + (k - n / 2) * 22 + R.uniform(-10, 10) - 20, base - h * R.uniform(0.75, 1.0))
        culms.append(((x, base), top))
    ic.shade(ic.mask("ellipse", (x0 - 60, base - 12, x0 + 60, base + 12)), alpha=0.4, blur=6)
    for (bx, by), (tx, ty) in culms:
        ic.line([(bx, by), (tx, ty)], 13, (96, 128, 56))
        ic.line([(bx - 3, by), (tx - 3, ty)], 5, (176, 200, 118, 220))
        for t in np.linspace(0.15, 0.85, 5):
            jx, jy = bx + (tx - bx) * t, by + (ty - by) * t
            ic.line([(jx - 8, jy), (jx + 8, jy)], 4, (60, 80, 36, 220))
    # leaf masses: soft elongated clumps near the upper part of each culm
    for (bx, by), (tx, ty) in culms:
        for t in (0.62, 0.95):
            px, py = bx + (tx - bx) * t, by + (ty - by) * t
            canopy(ic, px + R.uniform(-10, 14), py + 10, 46, 30, light="#a4c060", dark="#34521e", n=7)


def scrub(ic: Icon, x: float, y: float, r: float) -> None:
    """Low bush on the hill flank."""
    ic.shade(ic.mask("ellipse", (x - r, y - r * 0.2, x + r * 1.3, y + r * 0.35)), alpha=0.4, blur=6)
    canopy(ic, x, y - r * 0.4, r, r * 0.65, light="#86984e", dark="#2c3c1a", n=6)


def draw(ic: Icon) -> None:
    R = ic.random
    ic.grade["gamma"] = 0.98
    ic.grade["mute"] = 0.86

    top = TIERS - 1
    top_y = front_y(top, cx(top)) - D
    # hill body behind the terrace ends: scrubby slope
    left, right = [], []
    for i in range(TIERS):
        xl, xr = cx(i) - half(i), cx(i) + half(i)
        left.append((xl - 16, front_y(i, xl) + H * 0.5))
        left.append((xl + 18, front_y(i, xl) - D - 6))
        right.append((xr + 16, front_y(i, xr) + H * 0.5))
        right.append((xr - 18, front_y(i, xr) - D - 6))
    body = left + right[::-1]
    bm = ic.poly_mask(body)
    ic.fill(bm, "#7e8a4a", "#4a5028", (CX - HALF[0], CX + HALF[0]), vertical=False, noise=0.34, chroma=0.16)
    lay, d = layer()
    for _ in range(260):
        x, y = R.uniform(CX - HALF[0], CX + HALF[0]), R.uniform(top_y, Y0 + 60)
        r = R.uniform(6, 14)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(40, 52, 20, 120) if R.random() < 0.6 else (170, 186, 110, 90))
    composite(ic, lay, bm)

    # hilltop behind the top terrace: camphor tree, grass mound, farmhouse
    ht = half(top)
    hill = [(cx(top) - ht - 10, front_y(top, cx(top) - ht) + 4)]
    hill += [(cx(top) + x, top_y - 40 * math.cos(math.pi * x / (2 * (ht + 10))) ** 0.6) for x in np.linspace(-ht + 10, ht - 10, 20)]
    hill += [(cx(top) + ht + 10, front_y(top, cx(top) + ht) + 4)]
    timber(ic, (404, top_y), (396, top_y - 110), 22, "#6e5640", "#3a2a1c")
    canopy(ic, 420, top_y - 190, 170, 118, light="#74884a", dark="#26361a", n=24)
    ic.poly(hill, "#8a9a52", "#5a6a32", noise=0.3, edge=0)
    farmhouse(ic, 388, 690, top_y + 18)
    ic.shade(ic.mask("ellipse", (378, top_y + 6, 740, top_y + 36)), alpha=0.35, blur=8)

    # terraces from the top down, each overlapping the foot of the wall above it
    for i in reversed(range(TIERS)):
        terrace(ic, i)
    for i, x in ((4, cx(4) - half(4) * 0.6), (3, cx(3) - half(3) * 0.62), (2, cx(2) - half(2) * 0.58), (1, cx(1) - half(1) * 0.62)):
        spill(ic, i, x)

    # scrub breaking the lower flanks, then the bamboo clump on the lower right flank
    for x, i, r in ((CX - HALF[0] + 22, 0, 62), (CX - HALF[0] + 90, 0, 40), (cx(1) - half(1) + 8, 1, 50),
                    (cx(2) - half(2) + 12, 2, 36), (CX + HALF[0] - 34, 0, 58), (cx(3) + half(3) + 12, 3, 32)):
        scrub(ic, x, front_y(i, x) + H * 0.55, r)
    bx = cx(1) + half(1) - 36
    bamboo(ic, bx, front_y(1, bx) + 10, 4, 230)
