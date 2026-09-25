"""Coastal Fishery (ocean_fishery): a small fishing boat moored at a plank landing stage.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the boat with its small tanned sail and the nets hung to dry on poles. The landing carries a
basket of silver fish and a curing barrel. Everything stands on the vanilla flat water band.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE, SIZE

SEED = 7
REFS = ("fishing_village", "dock", "wharf", "protected_harbor")

WATER_TOP, WATERLINE = 690, 742  # back edge of the water band, where hulls and posts meet the water
WATER_LIGHT, WATER_DEEP = "#74b0c4", "#2c5c70"
BAND_SPAN = (WATER_TOP, 900)

BOW, STERN = 92, 584  # boat x extent
MAST_T = 0.45
DECK_L, DECK_R, DECK_TOP, DECK_FRONT, DECK_BASE = 540, 1000, 566, 604, 648
POSTS = (566, 700, 842, 978)
POLES = (620, 800, 980)
POLE_TOP = 232
WOOD = (118, 82, 52)


# ---------------------------------------------------------------- helpers (candidates for the kit)
def clipped(ic: Icon, mask: Image.Image, paint) -> None:
    """Run ``paint(ImageDraw)`` on a scratch layer and composite it only inside ``mask``."""
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    paint(ImageDraw.Draw(lay))
    clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def intersect(*masks: Image.Image) -> Image.Image:
    arr = np.asarray(masks[0])
    for m in masks[1:]:
        arr = np.minimum(arr, np.asarray(m))
    return Image.fromarray(arr)


def net(ic: Icon, pts, back="#9c7a48", back_dark="#543e24", cord=(40, 28, 16, 190), mesh=34) -> None:
    """Hung fishing net: tan cloth-like mass, fine dark diamond mesh, vertical drape folds."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, back, back_dark, (min(ys), max(ys)), noise=0.2)

    def lattice(d: ImageDraw.ImageDraw) -> None:
        for x in range(-SIZE, 2 * SIZE, mesh):
            d.line([(x, 0), (x + SIZE, SIZE)], fill=cord, width=5)
            d.line([(x, 0), (x - SIZE, SIZE)], fill=cord, width=5)

    clipped(ic, m, lattice)
    # drape folds: alternating dark and light vertical streaks
    for i, x in enumerate(np.arange(min(xs) + 22, max(xs), 38)):
        fold = ic.mask("rectangle", (x - 7, min(ys), x + 7, max(ys)))
        ic.shade(intersect(fold, m), (0, 0, 0) if i % 2 else (255, 240, 210), 0.35 if i % 2 else 0.1, blur=6)
    lo = min(ys)
    ic.shade(ic.poly_mask([(p[0], max(p[1], lo + (max(ys) - lo) * 0.5)) for p in pts]), alpha=0.25, blur=12)
    ic.outline(pts, 5)


def fish(ic: Icon, cx: float, cy: float, length: float, angle: float) -> None:
    """Silver fish: lens-shaped body with a forked tail, rotated by ``angle`` degrees."""
    a = np.radians(angle)
    ca, sa = np.cos(a), np.sin(a)

    def rot(px, py):
        return (cx + px * ca - py * sa, cy + px * sa + py * ca)

    h = length * 0.2
    ts = np.linspace(-0.5, 0.5, 14)
    top = [rot(t * length, -h * np.cos(np.pi * t) ** 0.8) for t in ts]
    bot = [rot(t * length, h * np.cos(np.pi * t) ** 0.8 * 0.8) for t in ts[::-1]]
    tail = [rot(0.46 * length, 0), rot(0.66 * length, -h * 1.1), rot(0.6 * length, 0), rot(0.66 * length, h * 1.0)]
    ic.poly(tail, "#aab4b8", "#6e7a80", edge=4)
    ic.poly(top + bot, "#e8ecea", "#7d8a90", edge=4)
    ic.line([rot(-0.3 * length, -h * 0.1), rot(0.35 * length, -h * 0.15)], 3, (80, 110, 125, 200))
    ex, ey = rot(-0.34 * length, -h * 0.25)
    ic.draw.ellipse((ex - 4, ey - 4, ex + 4, ey + 4), fill=(25, 25, 28, 255))


def basket(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Wicker basket, slightly tapered, with a woven texture."""
    w = x1 - x0
    body = [(x0, y0), (x1, y0), (x1 - w * 0.1, y1 - 14), (x1 - w * 0.2, y1), (x0 + w * 0.2, y1), (x0 + w * 0.1, y1 - 14)]
    ic.poly(body, "#b58d55", "#6c4e2c", (x0, x1), vertical=False)
    m = ic.poly_mask(body)

    def weave(d: ImageDraw.ImageDraw) -> None:
        for y in np.arange(y0 + 16, y1, 16):
            d.line([(x0, y), (x1, y)], fill=(60, 40, 20, 170), width=4)
        for x in np.arange(x0 + 14, x1, 22):
            d.line([(x, y0), (x + (x0 + w / 2 - x) * 0.18, y1)], fill=(60, 40, 20, 110), width=3)

    clipped(ic, m, weave)
    ic.outline(body)


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


# ---------------------------------------------------------------- water
def band_points():
    ts = np.linspace(0, 1, 30)
    pts = [(72, WATER_TOP), (968, WATER_TOP), (1006, 852)]
    pts += [(1006 - 988 * t, 852 + 40 * np.sin(np.pi * t)) for t in ts]
    pts += [(18, 852)]
    return pts


def water_front(ic: Icon, band: Image.Image, mask: Image.Image, top: float = WATERLINE) -> None:
    """Paint water over the part of ``mask`` below ``top`` so hulls and posts stand in the band."""
    cut = ic.mask("rectangle", (0, top, SIZE, SIZE))
    ic.fill(intersect(mask, cut, band), WATER_LIGHT, WATER_DEEP, BAND_SPAN, noise=0.10)


def foam(ic: Icon, band: Image.Image, x0: float, x1: float, y: float = WATERLINE) -> None:
    def strokes(d: ImageDraw.ImageDraw) -> None:
        for x in np.arange(x0, x1, 24):
            L = ic.random.uniform(20, 40)
            yy = y + ic.random.uniform(-4, 6)
            d.line([(x, yy), (x + L, yy)], fill=(232, 244, 245, 230), width=8)

    clipped(ic, band, strokes)


def surf(ic: Icon, band: Image.Image) -> None:
    """Vanilla-style white wave crests across the band."""
    def strokes(d: ImageDraw.ImageDraw) -> None:
        for row, y in enumerate(range(WATER_TOP + 40, 900, 36)):
            x = -40 + (row % 2) * 60
            while x < SIZE:
                L = ic.random.uniform(40, 90)
                yy = y + ic.random.uniform(-8, 8)
                d.arc((x, yy - 12, x + L, yy + 12), 200, 340, fill=(228, 242, 245, 200), width=6)
                d.line([(x + 10, yy + 10), (x + L - 10, yy + 10)], fill=(20, 50, 66, 120), width=5)
                x += L + ic.random.uniform(30, 80)

    clipped(ic, band, strokes)


# ---------------------------------------------------------------- the boat
def sheer(t):
    """Near gunwale: high bow at the left, lower stern at the right, sagging amidships."""
    return 470 * (1 - t) + 512 * t + 74 * np.sin(np.pi * t) ** 0.9


def depth(t):
    return 24 + 166 * np.sin(np.pi * t) ** 0.45


def boat(ic: Icon) -> Image.Image:
    ts = np.linspace(0, 1, 40)
    xs = BOW + (STERN - BOW) * ts
    g = [(x, sheer(t)) for x, t in zip(xs, ts)]
    far = [(x, sheer(t) - 50 * np.sin(np.pi * t) ** 0.7) for x, t in zip(xs, ts)]
    bottom = [(x, sheer(t) + depth(t)) for x, t in zip(xs, ts)]
    mast_x = BOW + (STERN - BOW) * MAST_T

    # mast, stays and a small square sail set on its yard, bellied by the wind
    ic.beam((mast_x, 132), (mast_x, 560), 24, WOOD)
    for p in ((BOW + 8, 470), (STERN - 4, 514)):
        ic.line([(mast_x, 150), p], 5, (58, 40, 26))
    y0l, y0r = (mast_x - 150, 214), (mast_x + 170, 184)
    foot_l, foot_r = (mast_x - 128, 404), (mast_x + 196, 392)
    ts_s = np.linspace(0, 1, 16)
    top_edge = [(y0l[0] + (y0r[0] - y0l[0]) * t, y0l[1] + (y0r[1] - y0l[1]) * t) for t in ts_s]
    right_edge = [(y0r[0] + (foot_r[0] - y0r[0]) * t + 34 * np.sin(np.pi * t), y0r[1] + (foot_r[1] - y0r[1]) * t)
                  for t in ts_s]
    foot = [(foot_r[0] + (foot_l[0] - foot_r[0]) * t, foot_r[1] + (foot_l[1] - foot_r[1]) * t - 26 * np.sin(np.pi * t))
            for t in ts_s]
    left_edge = [(foot_l[0] + (y0l[0] - foot_l[0]) * t + 14 * np.sin(np.pi * t), foot_l[1] + (y0l[1] - foot_l[1]) * t)
                 for t in ts_s]
    sail = top_edge + right_edge + foot + left_edge
    ic.fill(ic.poly_mask(sail), "#b87c42", "#72401e", (y0l[0], foot_r[0] + 30), vertical=False, noise=0.14)
    sm = ic.poly_mask(sail)
    for f in (0.2, 0.4, 0.6, 0.8):  # cloth seams
        a = (y0l[0] + (y0r[0] - y0l[0]) * f, y0l[1] + (y0r[1] - y0l[1]) * f)
        b = (foot_l[0] + (foot_r[0] - foot_l[0]) * f + 20 * np.sin(np.pi * f), foot_l[1] + (foot_r[1] - foot_l[1]) * f - 26 * np.sin(np.pi * f))
        ic.line([a, ((a[0] + b[0]) / 2 + 14, (a[1] + b[1]) / 2), b], 4, (72, 42, 26, 200))
    ic.shade(intersect(sm, ic.mask("rectangle", (mast_x + 60, 0, SIZE, SIZE))), alpha=0.22, blur=30)
    ic.outline(sail, 6)
    ic.beam((y0l[0] - 16, y0l[1] + 2), (y0r[0] + 16, y0r[1] - 2), 14, WOOD)
    ic.line([foot_r, (STERN - 8, 500)], 5, (58, 40, 26))

    # interior seen from the raised camera
    ic.poly(far + g[::-1], "#5e4029", "#3a2616", edge=0)
    for t in (0.26, 0.64):
        x = BOW + (STERN - BOW) * t
        ic.poly([(x - 34, sheer(t) - 48), (x + 6, sheer(t) - 48), (x + 16, sheer(t) - 6), (x - 26, sheer(t) - 6)],
                "#9c7048", "#6e4a2e", edge=4)
    ic.line(far, 12, (120, 84, 54))
    ic.line(far, 4, LINE)
    ic.beam((mast_x, 404), (mast_x, 556), 24, WOOD)
    # a net heaped in the stern
    heap = [(430, 520), (452, 480), (486, 470), (520, 478), (548, 496), (556, 520)]
    ic.poly(heap, "#a88c60", "#6a5234", edge=5)

    # hull side: painted top strake over brown clinker planks
    hull = g + bottom[::-1]
    hm = ic.poly_mask(hull)
    ic.fill(hm, "#9a6b44", "#553722", (440, 760))
    strake = g + [(x, sheer(t) + depth(t) * 0.26) for x, t in zip(xs[::-1], ts[::-1])]
    ic.fill(ic.poly_mask(strake), "#6c8a90", "#3f565c", (460, 620), noise=0.14)
    for f in (0.26, 0.46, 0.64, 0.82):
        ic.line([(x, sheer(t) + depth(t) * f) for x, t in zip(xs, ts)], 5, (48, 30, 18, 220))
    ic.shade(ic.poly_mask(g + [(x, y + 30) for x, y in g[::-1]]), alpha=0.3, blur=8)
    ic.shade(ic.poly_mask(bottom + [(x, sheer(t) + depth(t) * 0.55) for x, t in zip(xs[::-1], ts[::-1])]),
             alpha=0.25, blur=14)
    ic.outline(hull)
    ic.line(g, 18, LINE)
    ic.line(g, 10, (150, 108, 70))
    # stem and stern posts
    ic.beam((BOW + 4, 482), (BOW - 14, 424), 18, WOOD)
    ic.beam((STERN - 4, 524), (STERN + 8, 482), 16, WOOD)
    return hm.filter(ImageFilter.MaxFilter(9))


# ---------------------------------------------------------------- landing stage with drying nets
def landing(ic: Icon, band: Image.Image) -> None:
    posts = Image.new("L", (SIZE, SIZE), 0)
    for x in POSTS:
        ic.rect((x - 18, DECK_BASE - 6, x + 18, 800), "#7a5436", "#4a3120", vertical=False)
        ImageDraw.Draw(posts).rectangle((x - 24, DECK_BASE, x + 24, 812), fill=255)
    ic.shade(ic.mask("rectangle", (DECK_L, DECK_BASE, DECK_R, DECK_BASE + 40)), alpha=0.4, blur=10)
    water_front(ic, band, posts)
    for x in POSTS:
        foam(ic, band, x - 40, x + 32)

    # net poles (behind the deck) and the nets hung to dry between them
    for x in POLES:
        ic.beam((x, POLE_TOP), (x, DECK_TOP + 10), 18, WOOD)
    for i, (a, b) in enumerate(zip(POLES, POLES[1:])):
        ts = np.linspace(0, 1, 15)
        upper = [(a + (b - a) * t, POLE_TOP + 26 + 44 * np.sin(np.pi * t)) for t in ts]
        lower = []
        for j, t in enumerate(ts[::-1]):
            drop = 150 + 120 * np.sin(np.pi * t) ** 1.2 + (22 if j % 2 else 0) + ic.random.uniform(-6, 6)
            lower.append((a + (b - a) * t + ic.random.uniform(-3, 3), POLE_TOP + 26 + drop))
        net(ic, upper + lower)
        ic.line(upper, 7, (70, 52, 34))
        for t in np.linspace(0.12, 0.88, 5):
            fx, fy = a + (b - a) * t, POLE_TOP + 26 + 44 * np.sin(np.pi * t)
            ic.ellipse((fx - 14, fy - 10, fx + 14, fy + 10), "#c8894a", "#8a5528", edge=4)
    for x in POLES:
        ic.beam((x, POLE_TOP), (x, POLE_TOP + 44), 18, WOOD)
        ic.ellipse((x - 14, POLE_TOP - 10, x + 14, POLE_TOP + 10), "#a07650", "#6a4a30", edge=4)

    # deck: plank top seen from above, then the front beam
    top = [(DECK_L + 10, DECK_TOP), (DECK_R - 10, DECK_TOP), (DECK_R, DECK_FRONT), (DECK_L, DECK_FRONT)]
    ic.poly(top, "#b08458", "#8a6440")
    for x in np.arange(DECK_L + 40, DECK_R - 10, 44):
        ic.line([(x, DECK_TOP + 2), (x + (x - 770) * 0.04, DECK_FRONT - 2)], 4, (60, 38, 22, 200))
    ic.rect((DECK_L, DECK_FRONT, DECK_R, DECK_BASE), "#7a5436", "#4e3320")


def props(ic: Icon) -> None:
    # curing barrel at the right, basket heaped with silver fish in the middle of the landing
    ic.barrel(872, 424, 976, 590)
    basket(ic, 652, 500, 820, 594)
    ic.ellipse((648, 480, 824, 520), "#5a4128", "#3a2818", edge=5)
    for cx, cy, L, ang in ((690, 488, 96, -16), (752, 480, 100, 12), (790, 496, 84, -30),
                           (716, 504, 92, 8), (672, 506, 74, 30), (756, 506, 88, -6)):
        fish(ic, cx, cy, L, ang)
    fish(ic, 606, 584, 86, 4)
    # mooring rope from the stern post to the first landing post
    ic.draw.line([(STERN + 8, 490), (556, 540), (566, 574)], fill=(70, 52, 34, 255), width=7, joint="curve")


def draw(ic: Icon) -> None:
    pts = band_points()
    band = ic.poly_mask(pts)
    ic.fill(band, WATER_LIGHT, WATER_DEEP, BAND_SPAN, noise=0.10)
    surf(ic, band)
    ic.shade(ic.poly_mask(pts[3:-1] + [(18, 820), (1006, 820)]), alpha=0.35, blur=14)
    ic.outline(pts)

    hull_mask = boat(ic)
    water_front(ic, band, hull_mask)
    surf_hull = intersect(hull_mask, ic.mask("rectangle", (0, WATERLINE + 10, SIZE, SIZE)), band)
    surf(ic, surf_hull)
    foam(ic, band, BOW + 50, STERN - 20)
    landing(ic, band)
    props(ic)
    rim_darken(ic)
