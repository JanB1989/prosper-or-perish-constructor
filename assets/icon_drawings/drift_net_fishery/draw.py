"""Drift-Net Fishery (drift_net_fishery): a two-masted open boat paying a long drift net over its stern.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the tanned lugsail boat, larger than the Coastal Fishery's skiff, with the net heaped in
the stern and running over the gunwale into the sea as a long line of cork floats, the net curtain
hanging under them and a flagged dan buoy marking the far end. Same water band as the Coastal Fishery.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE, SIZE

SEED = 11
REFS = ("fishing_village", "dock", "smuggler_cove", "protected_harbor")

WATER_TOP, WATER_BOTTOM, SAG = 660, 876, 30
WATERLINE = 736
WATER_LIGHT, WATER_DEEP = "#74b0c4", "#2c5c70"

BOW, STERN = 40, 640
MAIN_T, MIZZEN_T = 0.36, 0.9
WOOD = (118, 82, 52)
ROPE = (70, 52, 34)


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


def sail(ic: Icon, yard0, yard1, clew, tack, belly: float, colors=("#a35a34", "#5a2a16"), seams: int = 4) -> Image.Image:
    """Tanned lugsail: yard edge, bellied leech, curved foot, cloth seams, shadowed after half."""
    ts = np.linspace(0, 1, 18)

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    top = [lerp(yard0, yard1, t) for t in ts]
    leech = [(lerp(yard1, clew, t)[0] + belly * math.sin(math.pi * t), lerp(yard1, clew, t)[1]) for t in ts]
    foot = [(lerp(clew, tack, t)[0], lerp(clew, tack, t)[1] - belly * 0.5 * math.sin(math.pi * t)) for t in ts]
    luff = [(lerp(tack, yard0, t)[0] + belly * 0.25 * math.sin(math.pi * t), lerp(tack, yard0, t)[1]) for t in ts]
    pts = top + leech + foot + luff
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], (min(p[0] for p in pts), max(p[0] for p in pts)), vertical=False, noise=0.16)

    def band(f0, f1, bulge):
        """Strip of cloth between the luff-to-leech fractions f0 and f1, bowed like the belly."""
        a = [(lerp(lerp(yard0, yard1, f0), lerp(tack, clew, f0), t)[0] + bulge * math.sin(math.pi * t),
              lerp(lerp(yard0, yard1, f0), lerp(tack, clew, f0), t)[1]) for t in ts]
        b = [(lerp(lerp(yard0, yard1, f1), lerp(tack, clew, f1), t)[0] + bulge * math.sin(math.pi * t),
              lerp(lerp(yard0, yard1, f1), lerp(tack, clew, f1), t)[1]) for t in ts]
        return ic.poly_mask(a + b[::-1])

    # luff to leech: bright cloth by the mast, a lit crest on the belly, the trailing third in shadow
    tint(ic, band(-0.1, 0.34, belly * 0.2), m, (255, 214, 170), 0.28, 22)
    tint(ic, band(0.38, 0.52, belly * 0.5), m, (255, 226, 190), 0.12, 16)
    tint(ic, band(0.6, 1.2, belly * 0.9), m, (30, 8, 0), 0.34, 26)
    tint(ic, band(0.86, 1.2, belly), m, (20, 4, 0), 0.22, 10)
    for k in range(1, seams + 1):
        f = k / (seams + 1)
        a, b = lerp(yard0, yard1, f), lerp(tack, clew, f)
        mid = ((a[0] + b[0]) / 2 + belly * (0.3 + 0.5 * f), (a[1] + b[1]) / 2)
        ic.line([a, mid, b], 4, (50, 24, 12, 150))
    # the loose leech: a thin lit hem along the curved trailing edge
    ic.line([(x - 5, y) for x, y in leech[2:-2]], 4, (230, 170, 120, 110))
    ic.outline(pts, 6)
    return m


# ---------------------------------------------------------------- water
def water(ic: Icon) -> Image.Image:
    band = ic.water_band(top=WATER_TOP, bottom=WATER_BOTTOM, sag=SAG, inset=46)
    # darker front lip, like the Coastal Fishery band
    ts = np.linspace(0, 1, 30)
    lip = [(1006 - 988 * t, WATER_BOTTOM + SAG * math.sin(math.pi * t)) for t in ts]
    ic.shade(ic.poly_mask(lip + [(18, WATER_BOTTOM - 34), (1006, WATER_BOTTOM - 34)]), alpha=0.32, blur=14)
    return band


# ---------------------------------------------------------------- the boat
def sheer(t):
    """Near gunwale: high bow at the left, a little lower stern, sagging amidships."""
    return 500 * (1 - t) + 532 * t + 70 * math.sin(math.pi * t) ** 0.9


def depth(t):
    return 30 + 196 * math.sin(math.pi * t) ** 0.42


def hull_x(t):
    return BOW + (STERN - BOW) * t


def rigging(ic: Icon) -> None:
    mx, zx = hull_x(MAIN_T), hull_x(MIZZEN_T)
    # mainmast with a big dipping lugsail, peak raised aft
    ic.beam((mx, 110), (mx, 580), 26, WOOD)
    ic.line([(mx, 130), (BOW + 6, sheer(0) - 6)], 5, (58, 40, 26))
    sail(ic, (mx - 150, 236), (mx + 190, 156), (mx + 240, 476), (mx - 170, 512), 58,
         colors=("#c86c40", "#6a2a14"))
    ic.beam((mx - 172, 242), (mx + 208, 152), 14, WOOD)
    ic.line([(mx + 250, 470), (hull_x(0.72), sheer(0.72) - 20)], 5, (58, 40, 26))
    # small mizzen at the stern
    ic.beam((zx, 280), (zx, 590), 18, WOOD)
    sail(ic, (zx - 64, 330), (zx + 60, 298), (zx + 90, 476), (zx - 56, 490), 24, seams=2,
         colors=("#b85e38", "#622a14"))
    ic.beam((zx - 74, 334), (zx + 72, 294), 10, WOOD)
    ic.line([(zx, 270), (STERN + 30, sheer(1) - 30)], 4, (58, 40, 26))


def boat(ic: Icon) -> Image.Image:
    ts = np.linspace(0, 1, 44)
    xs = [hull_x(t) for t in ts]
    g = [(x, sheer(t)) for x, t in zip(xs, ts)]
    far = [(x, sheer(t) - 58 * math.sin(math.pi * t) ** 0.7) for x, t in zip(xs, ts)]
    bottom = [(x, sheer(t) + depth(t)) for x, t in zip(xs, ts)]

    rigging(ic)

    # interior seen from the raised camera: dark bilge, thwarts, net heaped aft
    ic.poly(far + g[::-1], "#5e4029", "#3a2616", edge=0)
    for t in (0.2, 0.5):
        x = hull_x(t)
        ic.poly([(x - 34, sheer(t) - 54), (x + 8, sheer(t) - 54), (x + 18, sheer(t) - 8), (x - 26, sheer(t) - 8)],
                "#9c7048", "#6e4a2e", edge=4)
    ic.line(far, 12, (120, 84, 54))
    ic.line(far, 4, LINE)
    ic.beam((hull_x(MAIN_T), 470), (hull_x(MAIN_T), 580), 26, WOOD)
    ic.beam((hull_x(MIZZEN_T), 470), (hull_x(MIZZEN_T), 590), 18, WOOD)
    heap = [(hull_x(0.58), sheer(0.58) - 4), (hull_x(0.6), 498), (hull_x(0.66), 470), (hull_x(0.74), 466),
            (hull_x(0.82), 480), (hull_x(0.88), 520), (hull_x(0.88), sheer(0.88) - 2)]
    ic.net(heap, back="#a88c60", back_dark="#5e4a2e", mesh=26)
    for t in (0.63, 0.7, 0.77, 0.84):  # corks on the heap
        cork(ic, hull_x(t), 486 + 30 * abs(t - 0.72) * 6 + ic.random.uniform(-6, 6), 13)
    # a basket of herring amidships
    ic.basket(hull_x(0.36) + 30, 520, hull_x(0.36) + 130, 586)
    ic.ellipse((hull_x(0.36) + 26, 506, hull_x(0.36) + 134, 534), "#5a4128", "#3a2818", edge=4)
    for cx, cy, ang in ((0, 514, -14), (40, 510, 10), (70, 520, -30), (20, 526, 18)):
        ic.fish(hull_x(0.36) + 40 + cx, cy, 64, ang)

    # hull side: dark tarred top strake over brown clinker planks
    hull = g + bottom[::-1]
    hm = ic.poly_mask(hull)
    ic.fill(hm, "#9a6b44", "#553722", (460, 780))
    strake = g + [(x, sheer(t) + depth(t) * 0.24) for x, t in zip(xs[::-1], ts[::-1])]
    ic.fill(ic.poly_mask(strake), "#4e5a52", "#2e3632", (480, 640), noise=0.14)
    for f in (0.24, 0.42, 0.6, 0.78):
        ic.line([(x, sheer(t) + depth(t) * f) for x, t in zip(xs, ts)], 5, (48, 30, 18, 220))
    ic.shade(ic.poly_mask(g + [(x, y + 30) for x, y in g[::-1]]), alpha=0.3, blur=8)
    ic.shade(ic.poly_mask(bottom + [(x, sheer(t) + depth(t) * 0.55) for x, t in zip(xs[::-1], ts[::-1])]),
             alpha=0.28, blur=14)
    tint(ic, ic.mask("ellipse", (hull_x(0.1), sheer(0.3) + 30, hull_x(0.45), sheer(0.3) + 120)), hm,
         (255, 230, 190), 0.12, 20)
    ic.outline(hull)
    ic.line(g, 18, LINE)
    ic.line(g, 10, (150, 108, 70))
    ic.beam((BOW + 4, sheer(0) + 12), (BOW - 16, sheer(0) - 54), 20, WOOD)
    ic.beam((STERN - 4, sheer(1) + 10), (STERN + 10, sheer(1) - 40), 18, WOOD)
    return hm.filter(ImageFilter.MaxFilter(9))


# ---------------------------------------------------------------- the drift net
def float_line():
    """Cork line: into the sea at the stern, sweeping forward, then drifting back to the dan buoy."""
    return bezier([(676, 752), (768, 868), (890, 846), (950, 742)], 48)


def bezier(p, n: int = 24):
    ts = np.linspace(0, 1, n)
    p = [np.array(q, float) for q in p]
    return [tuple((1 - t) ** 3 * p[0] + 3 * (1 - t) ** 2 * t * p[1] + 3 * (1 - t) * t * t * p[2] + t ** 3 * p[3])
            for t in ts]


def ribbon(ic: Icon, path, w0: float, w1: float, dark, mid, lit) -> None:
    """A tapering bundle of wet net: dark underside, mid body, lit top edge, a hint of mesh."""
    n = len(path)
    left, right = [], []
    for i, (x, y) in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        if ny > 0:  # make the normal point up/left, towards the light
            nx, ny = -nx, -ny
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    pts = left + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, mid, dark, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.22)
    ic.shade(ic.intersect(ic.poly_mask(right + [(x, y) for x, y in path[::-1]]), m), (10, 6, 2), 0.45, blur=3)

    def knots(d: ImageDraw.ImageDraw) -> None:
        for x in range(-SIZE, 2 * SIZE, 18):
            d.line([(x, 0), (x + SIZE, SIZE)], fill=(34, 22, 10, 110), width=3)
            d.line([(x, 0), (x - SIZE, SIZE)], fill=(34, 22, 10, 110), width=3)

    ic.overlay(knots, m)
    ic.line(left[:-2], 5, lit)
    ic.outline(pts, 4, (40, 26, 14, 230))


def drift_net(ic: Icon, band: Image.Image) -> None:
    line = float_line()
    # the net curtain under the floats: a dark band just below the surface, fading with depth
    depth_px, steps = 84, 12
    for i in range(steps):
        f0, f1 = i / steps, (i + 1) / steps
        strip = [(x, y + 6 + depth_px * f0) for x, y in line] + [(x, y + 6 + depth_px * f1) for x, y in line[::-1]]
        ic.shade(ic.intersect(ic.poly_mask(strip), band), (6, 22, 32), 0.4 * (1 - f0))

    def strokes(d: ImageDraw.ImageDraw) -> None:
        for x, y in line[3:-2:2]:
            L = ic.random.uniform(56, 90)
            for s in range(6):
                a0, a1 = s / 6, (s + 1) / 6
                d.line([(x, y + 10 + L * a0), (x + 1, y + 10 + L * a1)], fill=(12, 34, 44, int(150 * (1 - a0))),
                       width=4)
            d.line([(x + 2, y + 12), (x + 2, y + 30)], fill=(196, 222, 226, 70), width=2)

    ic.overlay(strokes, band)
    # net and rope running from the stern heap over the rail and into the sea in sagging folds
    sx, sy = hull_x(0.86), sheer(0.86)
    rail = (STERN + 8, sheer(1) - 8)

    def fold(k: int):
        """Heap -> over the stern rail -> sagging down the outside of the stern into the sea."""
        up = bezier([(sx - 30 + 14 * k, sy - 46 + 12 * k), (sx + 20, sy - 64 + 10 * k),
                     (rail[0] - 20, rail[1] - 26 + 8 * k), (rail[0] + 4 * k, rail[1] + 4 * k)], 12)
        down = bezier([(rail[0] + 4 * k, rail[1] + 4 * k), (rail[0] + 46 - 10 * k, rail[1] + 40),
                       (706 - 12 * k, 650), (678 - 4 * k, 748)], 16)
        return up + down[1:]

    for k, (w0, w1, dark, mid) in enumerate(((30, 14, "#3a2a18", "#a08050"), (26, 12, "#2e2214", "#8c6c44"),
                                             (22, 10, "#342616", "#b08c5c"))):
        ribbon(ic, fold(k), w0, w1, dark, mid, (222, 194, 140, 230))
    ic.line([(x + 4, y + 2) for x, y in fold(1)], 6, ROPE)
    # splash and foam where the net enters the water
    tint(ic, ic.mask("ellipse", (636, 730, 724, 766)), band, (240, 250, 250), 0.55, 5)

    def splash(d: ImageDraw.ImageDraw) -> None:
        d.arc((640, 734, 704, 762), 110, 250, fill=(240, 250, 250, 230), width=7)
        d.arc((652, 738, 718, 764), 300, 60, fill=(240, 250, 250, 210), width=6)
        d.arc((648, 740, 708, 766), 20, 150, fill=(236, 248, 250, 150), width=5)
        for dx, dy, L in ((-50, 18, 28), (30, 14, 34), (-22, 26, 22)):
            d.line([(676 + dx, 746 + dy), (676 + dx + L, 746 + dy)], fill=(236, 248, 250, 210), width=6)
        for dx, dy, r in ((-28, -8, 5), (30, -12, 4), (-6, -18, 4), (16, -4, 3)):
            d.ellipse((676 + dx - r, 736 + dy - r, 676 + dx + r, 736 + dy + r), fill=(240, 250, 250, 220))

    ic.overlay(splash)
    for k, (x, y) in enumerate(line[3::4]):
        cork(ic, x, y - 3, 20 if k % 2 else 17)
    # dan buoy: a small keg with a pole and a dark flag at the far end of the net
    bx, by = 958, 744
    tint(ic, ic.mask("ellipse", (bx - 48, by - 4, bx + 60, by + 26)), band, (10, 30, 40), 0.35, 5)
    ic.beam((bx, by - 10), (bx - 10, 452), 14, WOOD)
    flag = [(bx - 8, 456), (bx + 46, 466), (bx + 28, 500), (bx + 48, 536), (bx - 6, 528)]
    ic.poly(flag, "#8a3a2a", "#4a1e16", edge=4)
    tint(ic, ic.poly_mask(flag[1:4] + [(bx + 10, 490)]), None, (0, 0, 0), 0.25, 4)
    keg = (bx - 36, by - 40, bx + 38, by + 14)
    ic.fill(ic.mask("ellipse", keg), "#c08650", "#5a3a1e", radial=(bx - 18, by - 36, 80), noise=0.14)
    for dy in (-26, -4):
        ic.line([(bx - 34, by + dy), (bx + 36, by + dy)], 6, (52, 52, 56))
    ic.overlay(lambda d: d.ellipse(keg, outline=LINE, width=5))
    ic.foam(bx - 50, bx + 44, by + 10)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.8
    band = water(ic)
    hull_mask = boat(ic)
    ic.waterline(hull_mask, WATERLINE)
    ic.foam(BOW + 60, STERN - 20, WATERLINE)
    drift_net(ic, band)
    rim_darken(ic)
