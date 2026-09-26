"""Offshore Fishery (offshore_fishery): a decked three-masted herring buss hauling its net at sea.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the big decked hull with a raised stern cabin, three masts with canvas square sails, salt
casks on deck, and a net full of silver herring hauled up the side while the cork line runs off
across darker, choppier open water. It is the top of the Coastal -> Drift-Net -> Offshore chain,
so it keeps their water band and colours but is clearly a ship, not a boat.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE, SIZE

SEED = 19
REFS = ("fishing_village", "dock", "shipyard", "trade_company_harbor")

WATER_TOP, WATER_BOTTOM, SAG = 662, 870, 32
WATERLINE = 738
WATER_LIGHT, WATER_DEEP = "#6aa2b8", "#244e62"

BOW, STERN = 92, 862
FORE_X, MAIN_X, MIZ_X = 262, 478, 760
WOOD = (118, 82, 52)
ROPE = (70, 52, 34)
RIG = (54, 38, 26)
CANVAS = ("#e2d4b2", "#9c8a66")


# ---------------------------------------------------------------- helpers (candidates for the kit)
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


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


def cork(ic: Icon, cx: float, cy: float, r: float, colors=("#d0935a", "#7a4822")) -> None:
    """Cork float riding the water: lit top-left, dark underside, a sliver of shadow on the water."""
    tint(ic, ic.mask("ellipse", (cx - r * 1.2, cy + r * 0.1, cx + r * 1.6, cy + r * 0.9)), None, (10, 30, 40), 0.35, 4)
    box = (cx - r, cy - r * 0.7, cx + r, cy + r * 0.7)
    ic.fill(ic.mask("ellipse", box), colors[0], colors[1], radial=(cx - r * 0.4, cy - r * 0.5, r * 1.9), noise=0.12)
    ic.overlay(lambda d: d.ellipse(box, outline=(46, 30, 16, 200), width=4))


def square_sail(ic: Icon, x0: float, x1: float, top: float, foot: float, belly: float = 30,
                colors=CANVAS, cloths: int = 5) -> Image.Image:
    """Square sail set on its yard, bellied towards the viewer: curved leeches and foot, cloth seams,
    a lit left half and a shadowed right half."""
    ts = np.linspace(0, 1, 20)
    head = [(x0 + (x1 - x0) * t, top) for t in ts]
    right = [(x1 + belly * 0.5 * math.sin(math.pi * t), top + (foot - top) * t) for t in ts]
    bottom = [(x1 - (x1 - x0) * t, foot + belly * math.sin(math.pi * t)) for t in ts]
    left = [(x0 - belly * 0.5 * math.sin(math.pi * t), foot - (foot - top) * t) for t in ts]
    pts = head + right + bottom + left
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], (x0, x1 + belly), vertical=False, noise=0.14)
    for k in range(1, cloths):
        f = k / cloths
        x = x0 + (x1 - x0) * f
        ic.line([(x, top + 4), (x + (f - 0.5) * belly * 0.8, (top + foot) / 2), (x, foot + belly * math.sin(math.pi * f) - 4)],
                3, (90, 72, 46, 150))
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, top, x1 + belly, foot + belly)), m, (0, 0, 0), 0.26, 30)
    tint(ic, ic.mask("rectangle", (x0 - belly, foot - (foot - top) * 0.35, x1 + belly, foot + belly)), m,
         (0, 0, 0), 0.14, 20)
    tint(ic, ic.mask("ellipse", (x0, top + 10, x0 + (x1 - x0) * 0.4, foot)), m, (255, 246, 220), 0.16, 24)
    ic.outline(pts, 6)
    ic.beam((x0 - 22, top - 2), (x1 + 22, top - 2), 16, WOOD)
    return m


def cask(ic: Icon, x0, y0, x1, y1, wood=("#b07c4e", "#4a2e18")) -> None:
    """Salt cask standing: bulged staves lit from the left, iron hoops, lit head."""
    w, h = x1 - x0, y1 - y0
    bul = w * 0.08
    ts = np.linspace(0, 1, 24)
    pts = [(x0 - bul * math.sin(math.pi * t), y0 + h * t) for t in ts]
    pts += [(x1 + bul * math.sin(math.pi * t), y0 + h * t) for t in ts[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], radial=(x0 + w * 0.25, y0 + h * 0.4, w * 1.0), noise=0.16)
    for f in (0.18, 0.82):
        y = y0 + h * f
        ic.line([(x0 - bul * 0.6, y), (x1 + bul * 0.6, y)], 8, (54, 54, 58))
    ic.outline(pts, 4)
    head = (x0 - 2, y0 - w * 0.2, x1 + 2, y0 + w * 0.2)
    ic.fill(ic.mask("ellipse", head), "#d0a878", "#8a6038", (head[1], head[3]), noise=0.14)
    ic.overlay(lambda d: d.ellipse(head, outline=LINE, width=4))


# ---------------------------------------------------------------- water
def water(ic: Icon) -> Image.Image:
    band = ic.water_band(top=WATER_TOP, bottom=WATER_BOTTOM, sag=SAG, inset=46, light=WATER_LIGHT, deep=WATER_DEEP)
    ts = np.linspace(0, 1, 30)
    lip = [(1006 - 988 * t, WATER_BOTTOM + SAG * math.sin(math.pi * t)) for t in ts]
    ic.shade(ic.poly_mask(lip + [(18, WATER_BOTTOM - 34), (1006, WATER_BOTTOM - 34)]), alpha=0.32, blur=14)
    # choppier open sea: a few extra dark troughs and white caps
    def chop(d: ImageDraw.ImageDraw) -> None:
        for _ in range(26):
            x, y = ic.random.uniform(20, 1000), ic.random.uniform(WATER_TOP + 20, WATER_BOTTOM + 10)
            L = ic.random.uniform(30, 60)
            d.line([(x, y), (x + L, y - 4)], fill=(236, 246, 246, 210), width=6)
            d.line([(x + 6, y + 9), (x + L + 10, y + 7)], fill=(16, 40, 54, 110), width=6)

    ic.overlay(chop, band)
    return band


# ---------------------------------------------------------------- the buss
def hx(t):
    return BOW + (STERN - BOW) * t


def smooth(a, b, t):
    u = min(max((t - a) / (b - a), 0), 1)
    return u * u * (3 - 2 * u)


def sheer(t):
    """Near rail: raised bow, low waist, a high stern castle at the right."""
    t = min(max(t, 0.0), 1.0)
    return 452 * (1 - t) + 468 * t + 46 * math.sin(math.pi * t) ** 0.8 - 30 * (1 - t) ** 6 - 66 * smooth(0.7, 0.8, t)


def keel(t):
    """Bottom of the hull (below the waterline): the stem curves up at the bow, square stern."""
    return 800 - 250 * max(0, 1 - t / 0.2) ** 2


def masts(ic: Icon) -> None:
    # standing rigging behind everything
    for x, top in ((FORE_X, 170), (MAIN_X, 70), (MIZ_X, 160)):
        for dx in (-110, 110):
            ic.line([(x, top + 30), (x + dx, sheer((x + dx - BOW) / (STERN - BOW)) - 20)], 4, RIG)
    ic.line([(MAIN_X, 90), (FORE_X, 190)], 4, RIG)
    ic.line([(FORE_X, 190), (18, 404)], 4, RIG)
    ic.line([(MAIN_X, 90), (MIZ_X, 170)], 4, RIG)
    for x, top, w in ((FORE_X, 160, 22), (MAIN_X, 60, 26), (MIZ_X, 150, 18)):
        ic.beam((x, top), (x, 540), w, WOOD)
    # main topsail and course, fore course, a small mizzen sail
    square_sail(ic, MAIN_X - 92, MAIN_X + 92, 96, 176, belly=16, cloths=3)
    square_sail(ic, MAIN_X - 150, MAIN_X + 150, 200, 390, belly=30)
    square_sail(ic, FORE_X - 118, FORE_X + 118, 214, 372, belly=26, cloths=4)
    square_sail(ic, MIZ_X - 64, MIZ_X + 64, 176, 250, belly=12, cloths=3)
    # pennant at the main truck, mast tops over the sails
    pen = [(MAIN_X + 4, 40), (MAIN_X + 110, 54), (MAIN_X + 4, 70)]
    ic.poly(pen, "#8a3a2a", "#4a1e16", edge=4)
    ic.beam((MAIN_X, 34), (MAIN_X, 96), 14, WOOD)
    ic.beam((FORE_X, 150), (FORE_X, 214), 18, WOOD)


def deck(ic: Icon, g, far) -> None:
    """Interior seen from the raised camera: deck planks, salt casks, coiled net, stern cabin."""
    ic.poly(far + g[::-1], "#8e6a46", "#5c4028", edge=0)
    dm = ic.poly_mask(far + g[::-1])

    def seams(d: ImageDraw.ImageDraw) -> None:
        for k in range(1, 4):
            f = k / 4
            d.line([(x, y1 + (y2 - y1) * f) for (x, y1), (_, y2) in zip(far, g)], fill=(50, 32, 18, 150), width=4)

    ic.overlay(seams, dm)
    ic.line(far, 12, (120, 84, 54))
    ic.line(far, 4, LINE)
    for x in (FORE_X, MAIN_X, MIZ_X):
        ic.beam((x, 400), (x, 540), 26 if x == MAIN_X else 20, WOOD)
    # salt casks between the fore and main masts, a coil of net aft of the main mast
    for x0, y0, s in ((300, 418, 1.0), (352, 426, 1.0), (404, 420, 0.95), (326, 448, 1.05), (378, 452, 1.0)):
        cask(ic, x0, y0, x0 + 50 * s, y0 + 72 * s)
    heap = [(540, 470), (556, 432), (596, 418), (640, 424), (668, 446), (672, 474)]
    ic.net(heap, back="#a88c60", back_dark="#5e4a2e", mesh=24)
    # stern cabin on the raised quarterdeck
    cab = (716, 312, 846, 402)
    ic.rect(cab, "#8e6c48", "#5e4630")
    tint(ic, ic.mask("rectangle", (cab[0] + 70, cab[1], cab[2], cab[3])), None, (0, 0, 0), 0.25, 12)
    ic.window(742, 340, 770, 372)
    roof = [(704, 318), (736, 272), (838, 268), (862, 314)]
    ic.poly(roof, "#6c4a32", "#3e2a1c", edge=6)
    ic.shade(ic.mask("rectangle", (cab[0], cab[1], cab[2], cab[1] + 22)), alpha=0.35, blur=6)
    ic.beam((850, 250), (850, 312), 12, WOOD)  # stern lantern post
    ic.ellipse((836, 222, 864, 256), "#c8a060", "#6a4a24", edge=4)


def buss(ic: Icon) -> Image.Image:
    ts = np.linspace(0, 1, 60)
    xs = [hx(t) for t in ts]
    g = [(x, sheer(t)) for x, t in zip(xs, ts)]
    far = [(x, sheer(t) - 58 * math.sin(math.pi * min(t, 0.97)) ** 0.5) for x, t in zip(xs, ts)]
    bottom = [(x, keel(t)) for x, t in zip(xs, ts)]

    # bowsprit behind the hull
    ic.beam((hx(0.06), sheer(0.06) + 10), (26, 396), 20, WOOD)
    masts(ic)
    deck(ic, g, far)

    hull = g + [(STERN + 14, sheer(1) + 10), (STERN + 4, keel(1))] + bottom[::-1]
    hm = ic.poly_mask(hull)
    ic.fill(hm, "#8a6040", "#4a3020", (440, 800))
    # tarred bottom planks, a painted band under the rail, two heavy wales
    ic.fill(ic.intersect(hm, ic.poly_mask([(0, 700), (SIZE, 690), (SIZE, SIZE), (0, SIZE)])), "#4a3a2c", "#2a2018",
            (690, 800), noise=0.14)
    band = g + [(x, sheer(t) + 40) for x, t in zip(xs[::-1], ts[::-1])]
    ic.fill(ic.intersect(hm, ic.poly_mask(band)), "#5c7462", "#34463a", (400, 540), noise=0.14)
    for f, w in ((0.2, 5), (0.34, 5), (0.5, 5), (0.66, 5)):
        ic.line([(x, sheer(t) + (keel(t) - sheer(t)) * f) for x, t in zip(xs, ts) if keel(t) - sheer(t) > 80], w,
                (48, 30, 18, 200))
    for off in (52, 118):
        wale = [(x, sheer(t) + off) for x, t in zip(xs, ts) if keel(t) - sheer(t) > off + 30]
        ic.line(wale, 20, (40, 28, 18))
        ic.line([(x, y - 5) for x, y in wale], 6, (140, 102, 66))
    # stern castle side: two dark windows
    for wx in (744, 806):
        ic.window(wx, sheer(0.9) + 14, wx + 26, sheer(0.9) + 40)
    ic.shade(ic.poly_mask(g + [(x, y + 34) for x, y in g[::-1]]), alpha=0.3, blur=8)
    tint(ic, ic.mask("ellipse", (hx(0.08), 480, hx(0.42), 640)), hm, (255, 228, 190), 0.12, 24)
    tint(ic, ic.mask("rectangle", (hx(0.78), 380, STERN + 40, 820)), hm, (0, 0, 0), 0.18, 20)
    ic.outline(hull)
    ic.line(g, 18, LINE)
    ic.line(g, 10, (156, 112, 72))
    ic.beam((BOW + 2, sheer(0) + 20), (BOW - 22, sheer(0) - 44), 22, WOOD)
    return hm.filter(ImageFilter.MaxFilter(9))


# ---------------------------------------------------------------- the net being hauled
def haul(ic: Icon, band: Image.Image) -> None:
    ts = np.linspace(0, 1, 40)
    line = [(690 + 280 * t, 772 + 34 * math.sin(math.pi * t * 0.9) - 20 * t) for t in ts]
    curtain = line + [(x + 6, y + 90) for x, y in line[::-1]]
    cm = ic.intersect(ic.poly_mask(curtain), band)

    def lattice(d: ImageDraw.ImageDraw) -> None:
        for x in range(-SIZE, 2 * SIZE, 24):
            d.line([(x, 0), (x + SIZE, SIZE)], fill=(196, 170, 120, 170), width=4)
            d.line([(x, 0), (x - SIZE, SIZE)], fill=(196, 170, 120, 170), width=4)

    ic.shade(cm, (30, 60, 70), 0.3)
    ic.overlay(lattice, cm)
    lower = [(x, y + 24) for x, y in line] + [(x + 6, y + 130) for x, y in line[::-1]]
    ic.shade(ic.intersect(ic.poly_mask(lower), band), WATER_DEEP, 0.8, blur=16)
    # the bag of herring hauled up the side, hanging from the rail
    bag = [(560, sheer(0.61) - 6), (650, sheer(0.72) - 8), (700, 640), (706, 720), (676, 770), (610, 784),
           (556, 760), (536, 690)]
    ic.net(bag, back="#a8845a", back_dark="#4e3a22", mesh=24)
    for cx, cy, L, a in ((580, 700, 70, 60), (612, 736, 76, -20), (650, 704, 66, 30), (628, 668, 60, -50),
                         (592, 748, 60, 10), (668, 742, 58, -40), (610, 610, 56, 70)):
        ic.fish(cx, cy, L, a)
    ic.shade(ic.poly_mask(bag), (60, 40, 20), 0.18)
    ic.line([(556, sheer(0.6) - 8), (548, 700), (604, 788), (690, 776)], 7, ROPE)
    ic.foam(560, 720, 776)
    for k, (x, y) in enumerate(line[3::4]):
        cork(ic, x, y - 3, 18 if k % 2 else 15)
    ic.foam(700, 980, 780)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.8
    band = water(ic)
    hull_mask = buss(ic)
    ic.waterline(hull_mask, WATERLINE)
    ic.foam(BOW + 40, STERN, WATERLINE)
    haul(ic, band)
    rim_darken(ic)
