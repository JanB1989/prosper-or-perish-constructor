"""Elephant Kraal (elephant_kraal): a grey elephant inside a timber stockade, a mahout's watch
platform and a pile of fodder.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/elephant_kraal/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/elephant_kraal

Identity: a big grey Asian elephant in profile (facing right, trunk reaching down to a heap of banana
leaves and cane) standing in front of a palisade of pointed logs; a thatched watch platform on stilts
at the left and a knee-high rail fence in front of the tower make it a pen, not a hunting ground.

Local helpers: ``tube`` (tapering body along a curve: trunk, tail), ``logs`` (palisade of pointed
bark-textured logs), ``thatch`` (from coffee_grove), ``rim_darken`` (from ocean_fishery).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 47
REFS = ("elephant_hunting_grounds", "stockade", "horse_breeders", "fulani_cattle_rearing_pen")

TIMBER = (116, 84, 56)
SKIN = ("#a08a72", "#261e16")
SKIN_FAR = ("#625444", "#221a14")
LEAF = ("#58782a", "#122204")


# ---------------------------------------------------------------- helpers
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*ms: Image.Image) -> Image.Image:
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


def tube(path, widths, n: int = 40) -> tuple[list, list, list]:
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    L = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / L, dx / L
    a = [(x + nx_ * w / 2, y + ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    b = [(x - nx_ * w / 2, y - ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    return a + b[::-1], a, b


def wrinkles(ic: Icon, mask: Image.Image, box, step: float, horizontal: bool = True, alpha: int = 70) -> None:
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        if horizontal:
            y = y0
            while y < y1:
                d.arc((x0 - 20, y - 10, x1 + 20, y + 14), 10, 170, fill=(30, 26, 24, alpha), width=3)
                d.arc((x0 - 20, y - 6, x1 + 20, y + 18), 20, 160, fill=(200, 194, 186, alpha // 2), width=2)
                y += step * rnd.uniform(0.7, 1.3)
        else:
            x = x0
            while x < x1:
                d.line([(x, y0 + rnd.uniform(0, 20)), (x + rnd.uniform(-10, 10), y1 - rnd.uniform(0, 20))],
                       fill=(30, 26, 24, alpha), width=3)
                x += step * rnd.uniform(0.7, 1.3)

    ic.overlay(paint, mask)


def logs(ic: Icon, x0: float, x1: float, base: float, top: float, w: float = 54) -> None:
    """Palisade of upright logs with rough pointed tops, per-log tone, bark streaks, a dark gap between."""
    rnd = ic.random
    x = x0
    while x < x1:
        lw = w * rnd.uniform(0.8, 1.15)
        t = top + rnd.uniform(-26, 26)
        tip = t - lw * rnd.uniform(0.5, 0.8)
        pts = [(x + 3, base), (x + 3, t), (x + lw * rnd.uniform(0.4, 0.6), tip), (x + lw - 3, t + rnd.uniform(-6, 6)),
               (x + lw - 3, base)]
        tone = rnd.uniform(0.88, 1.08)
        c1 = tuple(int(min(255, v * tone)) for v in (150, 116, 82))
        c2 = tuple(int(v * tone) for v in (70, 50, 34))
        ic.fill(ic.poly_mask(pts), c1, c2, (x, x + lw), vertical=False, noise=0.28)

        def bark(d, x=x, lw=lw, t=t):
            for _ in range(5):
                bx = rnd.uniform(x + 8, x + lw - 8)
                d.line([(bx, t + rnd.uniform(0, 40)), (bx + rnd.uniform(-4, 4), base - rnd.uniform(0, 60))],
                       fill=(40, 28, 18, 70), width=3)

        ic.overlay(bark, ic.poly_mask(pts))
        ic.shade(ic.poly_mask([(x + 3, t), pts[2], (x + lw * 0.5, t + 10), (x + 3, t + 20)]), (255, 236, 200), 0.18)
        ic.outline(pts, 4)
        x += lw


def thatch(ic: Icon, ridge, eave, c=("#c4a864", "#6c5226")) -> None:
    """Straw roof plane seen from above: stroke texture running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.3, 0.55, 0.8, 1.0]
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 20
        low = []
        for j in range(n + 1):
            t = j / n
            p = rl + (rr - rl) * t + ((el + (er - el) * t) - (rl + (rr - rl) * t)) * min(f1, 1.0)
            low.append((p[0] + rnd.uniform(-4, 4), p[1] + (rnd.uniform(-3, 7) if f1 < 1 else 0)))
        up = [tuple(rl + (el - rl) * f0 + np.array([-40, -4])), tuple(rr + (er - rr) * f0 + np.array([40, -4]))]
        band = ic.intersect(ic.poly_mask(up + low[::-1]), m)
        y0 = (rl + (el - rl) * f0)[1]
        y1 = max(p[1] for p in low)
        if f1 < 1:
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 20) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tint = rnd.uniform(0.92, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])),
                (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(160):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 24)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 22 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)
    ic.line([tuple(p) for p in ridge], 20, (104, 84, 50))


# ---------------------------------------------------------------- scene
def banana(ic: Icon) -> None:
    """Banana plant behind the palisade at the right: tropical clearing."""
    for deg, L, W, dr in ((-150, 230, 90, 0.2), (-100, 250, 88, 0.05), (-40, 240, 92, 0.3), (-20, 200, 80, 0.45),
                          (-75, 210, 84, 0.1)):
        ic.leaf((900, 330), deg, L, W, droop=dr, colors=("#7a9a3c", "#243a10"), rib=(150, 170, 90),
                vein=(40, 60, 20), edge=(30, 44, 14))
    ic.line([(900, 420), (904, 320)], 26, (80, 96, 44))


def tower(ic: Icon) -> None:
    """Mahout's watch platform on stilts at the left, thatched roof, ladder."""
    rnd = ic.random
    for x, top in ((64, 276), (286, 270)):
        ic.beam((x, 880), (x + rnd.uniform(-4, 4), top), 26, TIMBER)
    ic.beam((70, 640), (280, 420), 14, (100, 72, 48))
    # platform floor and railing
    ic.rect((34, 400, 318, 434), "#9a7048", "#5a3e24", edge=4)
    for x in (110, 170, 230):
        ic.beam((x, 400), (x, 350), 8, (110, 80, 52))
    ic.beam((50, 350), (300, 346), 10, (120, 88, 58))
    ic.shade(ic.mask("rectangle", (40, 434, 316, 480)), alpha=0.4, blur=12)
    ic.shade(ic.mask("rectangle", (34, 318, 318, 356)), (16, 10, 4), 0.7, blur=6)
    ridge = [(166, 104), (176, 98), (186, 104)]
    eave = [(x, 304 + rnd.uniform(-4, 5)) for x in np.linspace(12, 340, 14)]
    thatch(ic, ridge, eave)
    # the right slope turns from the light
    ic.shade(ic.poly_mask([(176, 96), (344, 304), (344, 336), (176, 336)]), (20, 12, 4), 0.3, blur=18)
    ic.shade(ic.poly_mask([(176, 100), (20, 304), (60, 304), (176, 140)]), (255, 240, 200), 0.12, blur=14)
    # ladder
    for x in (168, 214):
        ic.beam((x - 20, 880), (x, 434), 9, (124, 92, 60))
    for y in np.arange(480, 870, 56):
        f = (y - 434) / 446
        ic.beam((168 - 20 * f, y), (214 - 20 * f, y), 7, (124, 92, 60))


def fence(ic: Icon) -> None:
    """Knee-high rail fence in front of the watch tower: three posts with two lashed log rails."""
    posts = (36, 176, 318)
    for x in posts:
        ic.rect((x - 15, 758, x + 15, 892), "#8a6442", "#4a3220", vertical=False, edge=4)
        ic.ellipse((x - 15, 750, x + 15, 768), "#b08a60", "#7a5a3a", edge=3)
    for y in (790, 848):
        ic.rect((18, y - 15, 336, y + 15), "#a07a52", "#5a3e24", edge=4)
        ic.shade(ic.mask("rectangle", (18, y - 15, 336, y - 6)), (255, 236, 200), 0.2)
        for x in posts:
            ic.line([(x - 16, y - 13), (x + 16, y + 13)], 5, (70, 56, 36))
            ic.line([(x - 16, y + 13), (x + 16, y - 13)], 5, (70, 56, 36))


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def contour(ic: Icon, m: Image.Image, width: int = 7, alpha: float = 0.75) -> None:
    """Soft dark line just inside the edge of ``m`` (separates a form from what is behind it)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(width)))
    ic.shade(ring, (30, 24, 20), alpha, blur=1)


def elephant(ic: Icon) -> None:
    rnd = ic.random
    # far legs, in shadow
    far_hind = [(440, 600), (512, 600), (514, 840), (522, 870), (434, 872), (444, 840)]
    far_front = [(690, 600), (758, 600), (756, 842), (766, 868), (680, 870), (690, 840)]
    for leg in (far_hind, far_front):
        lm = ic.poly_mask(leg)
        ic.fill(lm, SKIN_FAR[0], SKIN_FAR[1], (600, 880), noise=0.26)
        wrinkles(ic, lm, (min(p[0] for p in leg), 660, max(p[0] for p in leg), 850), 30, alpha=50)
        contour(ic, lm, 7, 0.6)
    hind = [(346, 520), (492, 520), (486, 700), (478, 846), (490, 884), (374, 886), (384, 846), (374, 700)]
    front = [(626, 540), (752, 540), (748, 700), (740, 846), (754, 884), (632, 886), (644, 846), (636, 700)]
    path = [(850, 462), (892, 530), (918, 620), (934, 710), (946, 790), (938, 846), (908, 868), (882, 852),
            (878, 826)]
    trunk, ta, tb = tube(path, [136, 112, 92, 80, 68, 58, 50, 42, 36])
    parts = [ic.mask("ellipse", (326, 346, 792, 704)), ic.mask("ellipse", (392, 296, 730, 480)),
             ic.mask("ellipse", (684, 332, 900, 612)), ic.mask("ellipse", (724, 300, 822, 402)),
             ic.mask("ellipse", (780, 308, 874, 408)), ic.poly_mask([(716, 540), (860, 540), (846, 624), (770, 650)]),
             ic.poly_mask(hind), ic.poly_mask(front)]
    mass = smooth(union(*parts), 9)
    tm = smooth(ic.poly_mask(trunk), 3)
    whole = union(mass, tm)
    # the trunk casts a shadow on the palisade behind it
    ic.shade(ic.poly_mask([(x + 26, y + 10) for x, y in trunk]), (12, 8, 4), 0.55, blur=10)
    ic.fill(whole, SKIN[0], SKIN[1], radial=(440, 270, 560), noise=0.28, chroma=0.08)
    # volume: belly, underside of the head, lit back and forehead
    ic.shade(ic.intersect(mass, ic.mask("ellipse", (330, 570, 800, 770))), (16, 12, 8), 0.62, blur=24)
    # hind quarters and back legs turn away from the light
    ic.shade(ic.intersect(whole, ic.mask("ellipse", (300, 480, 560, 900))), (16, 12, 8), 0.3, blur=30)
    ic.shade(ic.intersect(whole, ic.mask("rectangle", (0, 560, SIZE, SIZE))), (150, 108, 76), 0.2, blur=30)
    # neck fold behind the head, lit forehead domes with a shadow under them
    ic.shade(ic.intersect(mass, ic.poly_mask([(650, 330), (700, 330), (690, 620), (640, 620)])), (18, 16, 14), 0.22,
             blur=18)
    ic.line([(700, 344), (684, 420), (680, 520), (690, 600)], 4, (30, 26, 22, 90))
    ic.shade(ic.intersect(whole, ic.mask("ellipse", (790, 380, 880, 430))), (18, 16, 14), 0.2, blur=10)
    ic.shade(ic.intersect(whole, ic.mask("ellipse", (380, 290, 700, 420))), (246, 238, 228), 0.2, blur=30)
    ic.shade(ic.intersect(whole, ic.mask("ellipse", (736, 296, 870, 390))), (246, 238, 228), 0.22, blur=16)
    ic.shade(ic.intersect(whole, ic.mask("rectangle", (330, 340, 390, 700))), (18, 16, 14), 0.25, blur=26)
    # legs: round shading, a contour where the leg passes in front of the belly, dust on the feet
    for leg in (hind, front):
        lm = ic.poly_mask(leg)
        xs = [p[0] for p in leg]
        x0, x1 = min(xs), max(xs)
        ic.shade(ic.intersect(lm, ic.mask("rectangle", (x1 - 40, 600, x1 + 10, 900))), (18, 16, 14), 0.35, blur=14)
        ic.shade(ic.intersect(lm, ic.mask("rectangle", (x0 + 10, 640, x0 + 34, 860))), (240, 232, 222), 0.15, blur=8)
        ic.shade(ic.intersect(lm, ic.mask("rectangle", (0, 790, SIZE, SIZE))), (130, 96, 64), 0.3, blur=12)
        wrinkles(ic, lm, (x0, 690, x1, 860), 26)
        ic.line([(x1 - 6, 640), (x1 - 2, 700), (x1 - 8, 846)], 4, (30, 26, 22, 150))
        ic.line([(x0 + 4, 690), (x0 + 12, 846)], 4, (30, 26, 22, 120))
        for k in range(3):  # toenails
            nx = x0 + 22 + k * (x1 - x0 - 44) / 2
            ic.fill(ic.mask("ellipse", (nx - 13, 862, nx + 13, 882)), "#9c8e7c", "#5e544a", noise=0.1)
    # dry skin mottling and folds
    for _ in range(110):
        x, y = rnd.uniform(340, 900), rnd.uniform(310, 700)
        r = rnd.uniform(6, 16)
        light = rnd.random() < 0.4
        ic.shade(ic.intersect(mass, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6))),
                 (228, 218, 208) if light else (24, 20, 18), 0.12, blur=3)
    for pts in (((636, 380), (622, 470), (640, 560)), ((430, 390), (410, 480), (416, 540)), ((520, 320), (530, 400))):
        ic.line(pts, 4, (34, 30, 28, 100))
    # trunk: shadowed front side, rings, pinkish mottled tip, a contour against the chest
    ic.shade(ic.intersect(tm, ic.poly_mask(tb + [(x - 26, y) for x, y in tb[::-1]])), (18, 16, 14), 0.35, blur=10)
    ic.shade(ic.intersect(tm, ic.poly_mask(ta + [(x + 14, y) for x, y in ta[::-1]])), (236, 220, 200), 0.22, blur=5)
    ic.shade(ic.intersect(tm, ic.mask("ellipse", (850, 800, 960, 890))), (200, 150, 140), 0.22, blur=10)
    wrinkles(ic, tm, (850, 540, 960, 800), 20)
    ic.line(ta[8:], 7, (24, 18, 14, 210))
    ic.line(tb[4:], 6, (24, 18, 14, 190))
    # mouth under the trunk base
    ic.line([(800, 612), (828, 626), (852, 622)], 5, (44, 36, 34, 170))
    # ear: rounded flap hanging behind the eye, casting shadow on the neck
    ear = [(690, 382), (736, 356), (784, 374), (798, 440), (792, 520), (764, 598), (740, 606), (728, 560), (700, 520),
           (682, 450)]
    ic.shade(ic.intersect(mass, ic.poly_mask([(p[0] - 30, p[1] + 16) for p in ear])), (10, 8, 6), 0.72, blur=12)
    ic.shade(ic.intersect(mass, ic.poly_mask([(p[0] - 6, p[1] + 30) for p in ear])), (10, 8, 6), 0.45, blur=10)
    em = ic.poly_mask(ear)
    ic.fill(em, "#a69078", "#3a2e24", radial=(700, 370, 280), noise=0.26, chroma=0.1)
    ic.shade(ic.intersect(em, ic.poly_mask([(740, 470), (820, 470), (812, 620), (730, 620)])), (190, 140, 130), 0.22,
             blur=12)
    for _ in range(26):
        x, y = rnd.uniform(740, 800), rnd.uniform(470, 600)
        ic.shade(ic.intersect(em, ic.mask("ellipse", (x - 5, y - 4, x + 5, y + 4))), (226, 190, 176), 0.35)
    ic.line([(706, 420), (722, 480), (718, 540)], 3, (40, 34, 30, 90))
    ic.outline(ear, 5, (30, 22, 16, 210))
    # eye with a wrinkled socket
    ic.fill(ic.mask("ellipse", (814, 428, 844, 450)), "#2a2624", "#121010")
    ic.draw.ellipse((822, 432, 828, 437), fill=(170, 160, 150, 255))
    ic.line([(810, 426), (830, 418), (850, 426)], 3, (34, 30, 28, 150))
    ic.line([(814, 456), (836, 462)], 3, (34, 30, 28, 110))
    # tail
    tail, _, _ = tube([(338, 470), (322, 540), (318, 620), (324, 660)], [20, 16, 12, 10])
    ic.poly(tail, "#7a726a", "#3a3634", edge=3)
    ic.poly([(312, 650), (336, 650), (342, 702), (308, 706)], "#3a3230", "#1e1a18", edge=3)
    contour(ic, whole, 7, 0.7)


def fodder(ic: Icon) -> None:
    """Heap of banana leaves, cut cane and a bunch of green bananas at the bottom right."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (820, 880, 1016, 944)), alpha=0.45, blur=10)
    for x0, y0, x1, y1 in ((820, 900, 1006, 846), (836, 910, 1010, 872), (826, 890, 996, 826)):
        ic.line([(x0, y0), (x1, y1)], 20, (40, 52, 20))
        ic.line([(x0, y0), (x1, y1)], 14, (150, 164, 80))
        for f in (0.3, 0.6, 0.85):
            px, py = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            ic.line([(px - 3, py - 8), (px + 3, py + 8)], 4, (70, 80, 34))
    for deg, L, W, base in ((200, 170, 76, (1000, 900)), (185, 160, 70, (990, 922)), (170, 140, 64, (1006, 930))):
        ic.leaf(base, deg, L, W, droop=0.12, colors=LEAF, rib=(140, 160, 80), vein=(40, 60, 20), edge=(30, 44, 14))
    ic.shade(ic.mask("ellipse", (860, 860, 1016, 944)), (8, 14, 2), 0.3, blur=14)
    for k in range(5):
        x = 846 + k * 18
        ic.poly([(x, 880), (x + 12, 876), (x + 22, 836), (x + 14, 832)], "#b8b44c", "#6a6a22", edge=3)


def ground(ic: Icon) -> None:
    rnd = ic.random
    top = [(16, 860)] + [(x, 840 + rnd.uniform(-10, 8)) for x in np.linspace(70, 960, 12)] + [(1008, 858)]
    pts = top + [(1010, 946), (520, 964), (14, 946)]
    ic.poly(pts, "#8a6a44", "#503a22", noise=0.32, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(860, 944)
        ic.shade(ic.mask("ellipse", (x - 14, y - 5, x + 14, y + 5)), (255, 230, 190) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)

    def grass(d):
        for _ in range(70):
            x, y = rnd.uniform(30, 990), rnd.uniform(850, 930)
            L = rnd.uniform(14, 30)
            d.line([(x, y), (x + rnd.uniform(-8, 8), y - L)], fill=(96, 124, 48, 220) if rnd.random() < 0.6
                   else (50, 70, 24, 220), width=4)

    ic.overlay(grass)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.84
    ic.grade["gamma"] = 0.64
    banana(ic)
    logs(ic, 300, 1006, 850, 330)
    ic.beam((300, 470), (1006, 460), 16, (104, 76, 50))
    ground(ic)
    ic.shade(ic.mask("ellipse", (340, 846, 900, 900)), alpha=0.5, blur=14)
    tower(ic)
    fodder(ic)
    elephant(ic)
    fence(ic)
    rim_darken(ic)
