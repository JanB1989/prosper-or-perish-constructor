"""Pearl Fishery (pearl_fishery): a pearling dhow over shallow turquoise oyster beds.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the dhow with its big lateen sail and lime-white bottom, a diver's rope and stone weight
over the side, and on a sandbank in front a basket of rough oysters and one opened oyster with a large
pearl. Same water band shape as the other fisheries, in shallow turquoise.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE, SIZE

SEED = 29
REFS = ("fishing_village", "dock", "kilwan_shipwrights", "smuggler_cove")

WATER_TOP, WATER_BOTTOM, SAG = 664, 866, 32
WATERLINE = 738
WATER_LIGHT, WATER_DEEP = "#64bab4", "#1e5e6c"

BOW, STERN = 84, 654
MAST_T = 0.44
WOOD = (122, 86, 54)
TEAK = ("#b07440", "#582e14")
ROPE = (92, 70, 44)
SAIL = ("#f2e2bc", "#a48660")


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


def pearl(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Lustrous pearl: cream sphere lit top-left, cool rim, bright specular dot, contact shadow."""
    tint(ic, ic.mask("ellipse", (cx - r * 0.8, cy + r * 0.35, cx + r * 1.4, cy + r * 1.25)), None, (40, 30, 40), 0.5,
         max(3, r * 0.12))
    box = (cx - r, cy - r, cx + r, cy + r)
    ic.fill(ic.mask("ellipse", box), "#ffffff", "#c4c0cc", radial=(cx - r * 0.35, cy - r * 0.4, r * 1.8), noise=0.02,
            chroma=0.02)
    tint(ic, ic.mask("ellipse", (cx - r * 0.1, cy + r * 0.25, cx + r * 1.1, cy + r * 1.1)), ic.mask("ellipse", box),
         (170, 160, 196), 0.35, r * 0.3)
    tint(ic, ic.mask("ellipse", (cx - r * 0.9, cy + r * 0.5, cx + r * 0.2, cy + r * 1.0)), ic.mask("ellipse", box),
         (255, 226, 214), 0.3, r * 0.2)  # warm bounce light from the nacre
    s = r * 0.24
    sx, sy = cx - r * 0.42, cy - r * 0.44
    tint(ic, ic.mask("ellipse", (sx - s * 2, sy - s * 2, sx + s * 2, sy + s * 2)), ic.mask("ellipse", box),
         (255, 255, 255), 0.6, s)
    ic.fill(ic.mask("ellipse", (sx - s, sy - s * 0.85, sx + s, sy + s * 0.85)), "#ffffff", noise=0, chroma=0)
    ic.overlay(lambda d: d.ellipse(box, outline=(70, 60, 70, 170), width=3))


def shell_ridges(ic: Icon, m: Image.Image, cx: float, cy: float, rx: float, ry: float, n: int = 5) -> None:
    """Concentric growth layers on a rough oyster shell."""
    def rings(d: ImageDraw.ImageDraw) -> None:
        for k in range(1, n + 1):
            f = k / (n + 1)
            a0 = ic.random.uniform(160, 200)
            box = (cx - rx * f, cy - ry * f, cx + rx * f, cy + ry * f)
            d.arc(box, a0, a0 + ic.random.uniform(140, 200), fill=(40, 34, 28, 150), width=4)
            d.arc((box[0] - 4, box[1] - 4, box[2] - 4, box[3] - 4), a0, a0 + 90, fill=(220, 210, 190, 80), width=3)

    ic.overlay(rings, m)


def oyster(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Closed rough oyster: jagged grey-brown shell with growth layers."""
    pts = ic.jitter(cx, cy, r, r * 0.72, 11, 0.16)
    m = ic.poly_mask(pts)
    ic.fill(m, "#9a9282", "#4a4238", radial=(cx - r * 0.5, cy - r * 0.6, r * 2.0), noise=0.3)
    shell_ridges(ic, m, cx + r * 0.3, cy + r * 0.3, r * 1.1, r * 0.8, 3)
    ic.outline(pts, 4, (40, 34, 28, 210))


def open_oyster(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Opened oyster: upper valve standing behind, lower cupped valve with nacre and a big pearl."""
    # upper valve, hinged at the back, its nacre face towards us
    up = ic.jitter(cx + r * 0.1, cy - r * 0.62, r * 0.9, r * 0.6, 20, 0.08)
    um = ic.poly_mask(up)
    ic.fill(um, "#6e6456", "#2e2820", radial=(cx - r * 0.4, cy - r * 1.1, r * 1.8), noise=0.4)
    inner = ic.jitter(cx + r * 0.12, cy - r * 0.56, r * 0.72, r * 0.45, 12, 0.06)
    im = ic.poly_mask(inner)
    ic.fill(im, "#fbf6f0", "#9eb0c4", radial=(cx - r * 0.3, cy - r * 0.9, r * 1.4), noise=0.05, chroma=0.3)
    tint(ic, ic.mask("ellipse", (cx - r * 0.2, cy - r * 0.9, cx + r * 0.6, cy - r * 0.3)), im, (240, 180, 220), 0.35, 14)
    tint(ic, ic.mask("ellipse", (cx + r * 0.2, cy - r * 0.8, cx + r * 0.8, cy - r * 0.4)), im, (150, 220, 210), 0.3, 12)
    ic.outline(up, 4, (40, 34, 28, 210))
    ridge = sorted((x + 3, y + 6) for x, y in up if y < cy - r * 0.8)
    if len(ridge) > 1:
        ic.overlay(lambda d: d.line(ridge, fill=(196, 186, 164, 170), width=5, joint="curve"), um)
    # lower valve: rough rim, nacre bowl, shadowed back
    low = ic.jitter(cx, cy, r, r * 0.55, 22, 0.06)
    lm = ic.poly_mask(low)
    ic.fill(lm, "#7a7060", "#2e2820", radial=(cx - r * 0.5, cy - r * 0.5, r * 2.0), noise=0.4)
    shell_ridges(ic, lm, cx + r * 0.1, cy + r * 0.1, r * 1.0, r * 0.56, 3)
    bowl = ic.jitter(cx, cy - r * 0.06, r * 0.78, r * 0.36, 18, 0.05)
    bm = ic.poly_mask(bowl)
    ic.fill(bm, "#fffaf4", "#a4b4c8", radial=(cx - r * 0.4, cy - r * 0.3, r * 1.4), noise=0.05, chroma=0.3)
    tint(ic, ic.mask("ellipse", (cx - r * 0.7, cy - r * 0.46, cx + r * 0.9, cy - r * 0.1)), bm, (40, 40, 70), 0.28, 12)
    tint(ic, ic.mask("ellipse", (cx + r * 0.1, cy - r * 0.2, cx + r * 0.8, cy + r * 0.3)), bm, (240, 170, 220), 0.35, 12)
    tint(ic, ic.mask("ellipse", (cx - r * 0.8, cy - r * 0.1, cx - r * 0.2, cy + r * 0.3)), bm, (140, 220, 210), 0.3, 12)
    ic.outline(low, 5, (30, 24, 20, 230))
    pearl(ic, cx - r * 0.02, cy - r * 0.12, r * 0.34)


def basket(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Round palm-leaf basket: rounded body, woven bands, rim, lit left."""
    w = x1 - x0
    ts = np.linspace(0, 1, 24)
    body = [(x0 + w * 0.5 - w * 0.5 * math.cos(math.pi * t) * (1 - 0.12 * t * t), y0 + (y1 - y0) * math.sin(math.pi * t / 2) ** 0.7 * 0)
            for t in ts]
    body = [(x0, y0)] + [(x0 + w * (0.5 - 0.5 * math.cos(math.pi * t)), y0) for t in ts[1:-1]] + [(x1, y0)]
    side = [(x1 - w * 0.08 * math.sin(math.pi * t / 2), y0 + (y1 - y0) * t) for t in ts]
    bottom = [(x1 - w * 0.08 - (w * 0.84) * t, y1 + 10 * math.sin(math.pi * t)) for t in ts]
    lside = [(x0 + w * 0.08 * math.sin(math.pi * (1 - t) / 2), y1 - (y1 - y0) * t) for t in ts]
    pts = side + bottom + lside
    m = ic.poly_mask(pts)
    ic.fill(m, "#c8a468", "#6a4e2a", radial=(x0 + w * 0.2, y0 + (y1 - y0) * 0.3, w * 1.1), noise=0.2)

    def weave(d: ImageDraw.ImageDraw) -> None:
        for y in np.arange(y0 + 14, y1 + 10, 18):
            d.line([(x0, y), (x1, y)], fill=(70, 46, 22, 160), width=4)
        for k, x in enumerate(np.arange(x0 + 10, x1, 20)):
            for y in np.arange(y0 + 14, y1 + 10, 36):
                d.line([(x, y + (k % 2) * 18), (x + 8, y + 18 + (k % 2) * 18)], fill=(240, 214, 160, 90), width=4)

    ic.overlay(weave, m)
    ic.outline(pts, 5)
    return m


# ---------------------------------------------------------------- water and sand
def water(ic: Icon) -> Image.Image:
    band = ic.water_band(top=WATER_TOP, bottom=WATER_BOTTOM, sag=SAG, inset=46, light=WATER_LIGHT, deep=WATER_DEEP)
    ts = np.linspace(0, 1, 30)
    lip = [(1006 - 988 * t, WATER_BOTTOM + SAG * math.sin(math.pi * t)) for t in ts]
    ic.shade(ic.poly_mask(lip + [(18, WATER_BOTTOM - 34), (1006, WATER_BOTTOM - 34)]), alpha=0.28, blur=14)
    # pale patches of sand showing through the shallows
    for cx, cy, rx in ((180, 800, 120), (430, 830, 90), (760, 700, 110)):
        tint(ic, ic.mask("ellipse", (cx - rx, cy - rx * 0.25, cx + rx, cy + rx * 0.25)), band, (230, 220, 170), 0.25, 18)
    return band


def sandbank(ic: Icon, band: Image.Image) -> Image.Image:
    ts = np.linspace(0, 1, 40)
    # a low spit rising out of the shallows: soft S-curve from front-left to the back right
    top = [(400 + 620 * t, 920 - 210 * (3 * t * t - 2 * t ** 3) ** 0.8 + 5 * math.sin(11 * t)) for t in ts]
    pts = top + [(1024, 1024), (400, 1024)]
    m = ic.intersect(ic.poly_mask(pts), band)
    ic.fill(m, "#e6d09c", "#a08458", (700, 900), noise=0.24)
    for _ in range(50):
        x, y = ic.random.uniform(460, 1000), ic.random.uniform(720, 900)
        tint(ic, ic.mask("ellipse", (x - 6, y - 3, x + 6, y + 3)), m, (70, 54, 34), 0.35)
    # damp strip along the waterline, a thin foam line just off it
    wet = top + [(x + 6, y + 34) for x, y in top[::-1]]
    tint(ic, ic.poly_mask(wet), m, (74, 56, 34), 0.45, 8)
    ic.overlay(lambda d: d.line([(x, y - 2) for x, y in top], fill=(250, 238, 200, 150), width=5), band)
    ic.overlay(lambda d: d.line([(x - 6, y - 10) for x, y in top], fill=(236, 248, 246, 230), width=7, joint="curve"),
               band)
    ic.overlay(lambda d: d.line([(x - 14, y - 24) for x, y in top[4:-6:2]], fill=(236, 248, 246, 110), width=4,
                                joint="curve"), band)
    return m


# ---------------------------------------------------------------- the dhow
def hx(t):
    return BOW + (STERN - BOW) * t


def sheer(t):
    """Near rail: long raking bow rising at the left, high square stern at the right."""
    t = min(max(t, 0.0), 1.0)
    return 530 + 58 * math.sin(math.pi * t) ** 0.8 - 110 * (1 - t) ** 3 - 96 * t ** 4


def keel(t):
    t = min(max(t, 0.0), 1.0)
    return 800 - 330 * max(0.0, 1 - t / 0.45) ** 2 - 40 * t ** 6


def lateen(ic: Icon) -> None:
    mx = hx(MAST_T)
    tack, peak, clew = (BOW - 34, 418), (mx + 250, 34), (hx(0.93), 470)
    f = (mx - 24 - tack[0]) / (peak[0] - tack[0])
    top = tack[1] + (peak[1] - tack[1]) * f + 20 * math.sin(math.pi * f) - 14
    ic.beam((mx + 6, 580), (mx - 24, top), 26, WOOD)  # mast raked forward, ending at the yard
    ic.line([(mx - 20, top + 20), (BOW - 50, sheer(0) - 34)], 5, (70, 50, 32))
    ic.line([(mx - 20, top + 20), (hx(0.98), sheer(1) - 10)], 5, (70, 50, 32))
    ts = np.linspace(0, 1, 20)
    yard = [(tack[0] + (peak[0] - tack[0]) * t, tack[1] + (peak[1] - tack[1]) * t + 20 * math.sin(math.pi * t))
            for t in ts]
    leech = [(peak[0] + (clew[0] - peak[0]) * t + 46 * math.sin(math.pi * t), peak[1] + (clew[1] - peak[1]) * t)
             for t in ts]
    foot = [(clew[0] + (tack[0] - clew[0]) * t, clew[1] + (tack[1] - clew[1]) * t + 40 * math.sin(math.pi * t))
            for t in ts]
    pts = yard + leech + foot
    m = ic.poly_mask(pts)
    ic.fill(m, SAIL[0], SAIL[1], (tack[0], clew[0] + 40), vertical=False, noise=0.14)
    for f in (0.22, 0.4, 0.58, 0.76):  # cloths run parallel to the leech
        a = (tack[0] + (peak[0] - tack[0]) * f, tack[1] + (peak[1] - tack[1]) * f + 20 * math.sin(math.pi * f))
        b = (clew[0] + (tack[0] - clew[0]) * (1 - f), clew[1] + (tack[1] - clew[1]) * (1 - f) + 40 * math.sin(math.pi * f))
        ic.line([a, ((a[0] + b[0]) / 2 + 20, (a[1] + b[1]) / 2), b], 4, (110, 94, 66, 150))
    # luff (the yard) light, leech in shadow, a lit crest on the belly between
    def inset(f):
        return [(x + (clew[0] - x) * f, y + (clew[1] - y) * f) for x, y in yard]
    tint(ic, ic.poly_mask(yard + inset(0.3)[::-1]), m, (255, 240, 200), 0.26, 22)
    tint(ic, ic.poly_mask(inset(0.4) + inset(0.52)[::-1]), m, (255, 244, 214), 0.12, 14)
    tint(ic, ic.poly_mask(leech + [(mx + 40, 400), (mx + 20, 300)]), m, (40, 20, 0), 0.34, 30)
    tint(ic, ic.poly_mask(leech[2:-2] + [(x - 40, y) for x, y in leech[-3:1:-1]]), m, (30, 14, 0), 0.2, 8)
    ic.outline(pts, 6)
    ic.beam((tack[0] - 14, tack[1] + 16), (peak[0] + 20, peak[1] - 16), 16, WOOD)
    ic.line([clew, (hx(0.97), sheer(0.97) - 6)], 5, (70, 50, 32))


def dhow(ic: Icon) -> Image.Image:
    ts = np.linspace(0, 1, 50)
    xs = [hx(t) for t in ts]
    g = [(x, sheer(t)) for x, t in zip(xs, ts)]
    far = [(x, sheer(t) - 54 * math.sin(math.pi * t) ** 0.6) for x, t in zip(xs, ts)]
    bottom = [(x, keel(t)) for x, t in zip(xs, ts)]

    lateen(ic)
    # interior: dark bilge, thwarts, a coil of diving rope and a little stern deck
    ic.poly(far + g[::-1], "#5e4029", "#3a2616", edge=0)
    for t in (0.26, 0.58):
        x = hx(t)
        ic.poly([(x - 30, sheer(t) - 50), (x + 8, sheer(t) - 50), (x + 16, sheer(t) - 6), (x - 22, sheer(t) - 6)],
                "#b08050", "#704c2e", edge=4)
    ic.line(far, 12, (138, 98, 62))
    ic.line(far, 4, LINE)
    ic.beam((hx(MAST_T) + 6, 470), (hx(MAST_T), 580), 26, WOOD)
    c = (hx(0.3), sheer(0.3) - 26)
    ang = np.linspace(0, 2.6 * 2 * math.pi, 90)
    spiral = [(c[0] + (46 - 2.6 * a) * math.cos(a), c[1] + (46 - 2.6 * a) * 0.42 * math.sin(a)) for a in ang]
    ic.ellipse((c[0] - 52, c[1] - 18, c[0] + 56, c[1] + 26), "#3a2616", "#2a1a0e", edge=0)
    ic.line(spiral, 11, (66, 46, 26))
    ic.line([(x - 1, y - 3) for x, y in spiral], 5, (188, 150, 96))
    ic.basket(hx(0.7) - 40, 492, hx(0.7) + 40, 548)
    for dx in (-20, 4, 26):
        oyster(ic, hx(0.7) + dx, 492, 20)

    stem = [(BOW - 58, sheer(0) - 36), (BOW - 30, sheer(0) - 8)]
    transom = [(STERN + 26, sheer(1) - 4), (STERN + 22, sheer(1) + 70), (STERN + 6, keel(1) - 10)]
    hull = stem + g + transom + bottom[::-1] + [(BOW - 22, sheer(0) + 40)]
    hm = ic.poly_mask(hull)
    ic.fill(hm, TEAK[0], TEAK[1], (440, 800))
    # lime-white bottom coating and a dark rubbing strake
    lime = [(x, max(keel(t) - 70, WATERLINE - 30)) for x, t in zip(xs, ts)]
    ic.fill(ic.intersect(hm, ic.poly_mask(lime + [(STERN + 40, 900), (0, 900)])), "#d8d0bc", "#8e887a", (650, 800),
            noise=0.18)
    for f in (0.3, 0.52):
        ic.line([(x, sheer(t) + (keel(t) - sheer(t)) * f) for x, t in zip(xs, ts) if keel(t) - sheer(t) > 60], 5,
                (60, 38, 20, 200))
    wale = [(x, sheer(t) + 34) for x, t in zip(xs, ts) if keel(t) - sheer(t) > 60]
    ic.line(wale, 16, (58, 36, 20))
    ic.line([(x, y - 4) for x, y in wale], 5, (176, 128, 80))
    ic.shade(ic.poly_mask(g + [(x, y + 30) for x, y in g[::-1]]), alpha=0.3, blur=8)
    tint(ic, ic.mask("ellipse", (hx(0.1), 520, hx(0.5), 660)), hm, (255, 230, 190), 0.14, 24)
    tint(ic, ic.mask("rectangle", (hx(0.8), 400, STERN + 40, 820)), hm, (0, 0, 0), 0.2, 20)
    ic.outline(hull)
    ic.line(g, 18, LINE)
    ic.line(g, 10, (170, 124, 78))
    # squared transom face in shadow, long raking stem head, sternpost standing proud of the rail
    face = [(STERN + 2, sheer(1) + 4), (STERN + 26, sheer(1) - 4), (STERN + 22, sheer(1) + 70), (STERN + 4, sheer(1) + 80)]
    ic.poly(face, "#6a4424", "#3a2212", edge=4)
    ic.beam((hx(0.14), keel(0.14) - 10), (BOW - 66, sheer(0) - 44), 20, WOOD)
    ic.beam((STERN + 2, sheer(1) + 90), (STERN + 36, sheer(1) - 50), 20, WOOD)
    return hm.filter(ImageFilter.MaxFilter(9))


def diver_line(ic: Icon, band: Image.Image) -> None:
    """Diver's rope over the side with a stone weight showing through the shallows."""
    x0, y0 = hx(0.54), sheer(0.54) - 4
    ic.beam((x0 - 40, y0 - 20), (x0 + 70, y0 + 6), 12, WOOD)  # short spar over the rail
    x1 = x0 + 62
    ic.line([(x1, y0 + 4), (x1 + 4, WATERLINE + 20)], 9, ROPE)
    under = ic.mask("rectangle", (x1 - 30, WATERLINE + 20, x1 + 34, WATERLINE + 90))
    ic.line([(x1 + 4, WATERLINE + 20), (x1 + 8, WATERLINE + 64)], 8, (60, 90, 96, 180))
    st = ic.jitter(x1 + 8, WATERLINE + 80, 28, 20, 8, 0.12)
    ic.fill(ic.intersect(ic.poly_mask(st), band), "#6a7a78", "#2e4a52", noise=0.2)
    ic.overlay(lambda d: d.ellipse((x1 - 22, WATERLINE + 12, x1 + 30, WATERLINE + 30), outline=(236, 248, 246, 220),
                                   width=6), band)
    del under


def beds(ic: Icon, band: Image.Image) -> None:
    sand = sandbank(ic, band)
    tint(ic, ic.mask("ellipse", (786, 760, 950, 810)), sand, (40, 30, 20), 0.45, 10)
    basket(ic, 796, 650, 932, 790)
    ic.fill(ic.mask("ellipse", (796, 634, 932, 668)), "#5a4128", "#3a2818")
    for cx, cy, r in ((826, 648, 28), (878, 638, 30), (914, 652, 24), (852, 664, 26), (900, 668, 22)):
        oyster(ic, cx, cy, r)
    tint(ic, ic.mask("ellipse", (470, 820, 840, 900)), sand, (40, 30, 20), 0.45, 12)
    open_oyster(ic, 640, 784, 176)
    for cx, cy, r in ((876, 846, 17), (906, 862, 14), (852, 870, 12)):
        pearl(ic, cx, cy, r)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.8
    ic.grade["mute"] = 0.9
    band = water(ic)
    hull_mask = dhow(ic)
    ic.waterline(hull_mask, WATERLINE)
    tint(ic, ic.intersect(hull_mask, ic.mask("rectangle", (0, WATERLINE + 4, SIZE, SIZE))), None, (200, 230, 220),
         0.12)
    ic.foam(BOW + 150, STERN, WATERLINE)
    diver_line(ic, band)
    beds(ic, band)
    rim_darken(ic)
