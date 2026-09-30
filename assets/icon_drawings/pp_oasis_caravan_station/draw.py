"""Oasis Caravan Station (pp_oasis_caravan_station): Saharan oasis stop on a salt-caravan route.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pp_oasis_caravan_station/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pp_oasis_caravan_station

Identity: two tall date palms over a low red mud-brick house (rounded corners, toron beams, a
flat roof with a crenellated parapet), a stone-kerbed well with a palm-trunk pulley frame and a
leather bucket, and a dromedary carrying lashed slabs of rock salt and goatskins (Tuareg salt
caravan). Palms, the well and the red earth keep it apart from the sandstone Caravanserai.
Caravan-family helpers copied from pp_caravanserai (see there), including ``camel``; local:
``frond``, ``palm``, ``house``, ``well``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("trans_saharan_trade_outposts", "caravan_stop", "caravanserai", "tambo")

BASE = 890
GROUND = 946
MUD = ("#c8804e", "#7a4424")
LEAF = ("#7c9a40", "#23380e")


# ---------------------------------------------------------------- caravan-family helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tone(c, f: float) -> tuple[int, int, int]:
    return tuple(int(min(255, max(0, v * f))) for v in rgb(c))


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def rim(ic: Icon, m: Image.Image, width: int = 4, color=(40, 24, 12), alpha: float = 0.75) -> None:
    """Soft dark edge just inside a mask (a form's contour without a hard outline)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(2 * width + 1)))
    ic.shade(ring, color, alpha, blur=1)


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def tube(path, widths, n: int = 40):
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    ln = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / ln, dx / ln
    a = [(x + nx_ * w / 2, y + ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    b = [(x - nx_ * w / 2, y - ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    return a + b[::-1], a, b


def hair(ic: Icon, mask: Image.Image, box, n: int, length: float = 14, light=(255, 236, 206), dark=(30, 16, 8),
         alpha: int = 60) -> None:
    """Short coat strokes (hair lying back and down) clipped to ``mask``."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            t = rnd.uniform(-1, 1)
            col = light + (int(t * alpha),) if t > 0 else dark + (int(-t * alpha),)
            d.line([(x, y), (x + rnd.uniform(-4, 4), y + length * rnd.uniform(0.6, 1.2))], fill=col, width=3)

    ic.overlay(paint, mask)


def modelled(ic: Icon, m: Image.Image, s: float, light=(255, 222, 170), lit: float = 0.4, dark: float = 0.5) -> None:
    """Round an animal's flat mask: warm light along every upper-left edge, dark underside."""
    edge = ImageChops.subtract(m, ImageChops.offset(m, int(12 * s) + 1, int(26 * s) + 1))
    tint(ic, edge, m, light, lit, 7 * s)
    under = ImageChops.subtract(m, ImageChops.offset(m, -int(6 * s), -int(30 * s) - 1))
    tint(ic, under, m, (12, 6, 2), dark, 10 * s)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.0, long: float = 1.0) -> None:
    """Coursed stone where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.85, 1.12)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.4, 2.4) * long
            j = lambda: rnd(-2, 2)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(70, 60, 44, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 50)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(40, 26, 14, shadow), width=5)
            x += w
        y += h
    paste_clipped(ic, lay, m)


def pointed(x0: float, x1: float, spring: float, bottom: float, k: float = 0.82, n: int = 18) -> list:
    """Two-centred pointed arch opening from ``bottom`` up to the springing line and the apex."""
    w = x1 - x0
    r = w * k
    mid = (x0 + x1) / 2
    th_mid = math.acos((mid - x0 - r) / r)
    left = [(x0 + r + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, th_mid, n)]
    right = [(x1 - (px - x0), py) for px, py in left[::-1]]
    return [(x0, bottom)] + left + right[1:] + [(x1, bottom)]


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.14, base - h * 0.8), (nx - w * 0.1, base - h * 1.02), (nx - w * 0.2, base - h * 1.12),
            (nx + w * 0.02, base - h * 1.08), (nx + w * 0.2, base - h * 1.14), (nx + w * 0.12, base - h * 1.0),
            (nx + w * 0.15, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.13, base - h * 0.96), (nx + w * 0.13, base - h * 0.95)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))


def rope(ic: Icon, pts, width: int = 6, color=(176, 146, 100)) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, color)


def road(ic: Icon, top: float, bot: float, c=("#c9a878", "#8e7048"), x0: float = 16, x1: float = 1008,
         ruts: bool = False) -> Image.Image:
    """Dusty ground band with pebbles, hoof marks and a shaded far edge; returns its mask."""
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def marks(d: ImageDraw.ImageDraw) -> None:
        if ruts:
            for y in (top + (bot - top) * 0.45, top + (bot - top) * 0.78):
                x = x0 + 10
                while x < x1 - 10:
                    ln = rnd(60, 160)
                    d.line([(x, y + rnd(-3, 3)), (x + ln, y + rnd(-3, 3))], fill=(50, 36, 20, 110), width=int(rnd(6, 9)))
                    x += ln + rnd(10, 50)
        for _ in range(70):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 8, bot - 8)
            r = rnd(3, 8)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(236, 220, 186, 130))
            d.line([(x - r, y + r * 0.6), (x + r, y + r * 0.6)], fill=(50, 36, 20, 110), width=2)
        for _ in range(26):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 10, bot - 10)
            d.arc((x - 9, y - 5, x + 9, y + 5), 0, 180, fill=(60, 44, 24, 100), width=3)

    ic.overlay(marks, m)
    tint(ic, ic.mask("rectangle", (0, top, SIZE, top + 24)), m, (0, 0, 0), 0.32, 10)
    ic.outline(pts, 5)
    return m


# ---------------------------------------------------------------- dromedary
def camel(ic: Icon, X: float, G: float, s: float = 0.6, left: bool = True, load: str = "bales",
          coat=("#cfa66c", "#5a3c20")) -> Image.Image:
    """Dromedary in profile, near fore foot at local x 40..100 standing on ``G``; head to the left
    unless ``left`` is False. ``load``: "bales" (two bales over a striped kilim, a rolled carpet on
    top) or "salt" (two lashed salt slabs on the flank, a slab edge showing above, goatskins).
    Local units, y up; returns the animal mask."""
    f = 1 if left else -1

    def P(pts):
        return [(X + f * x * s, G - y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def shift(pts, dx, dy=0):
        return [(x + dx, y + dy) for x, y in pts]

    # hoof contact shadows
    for hx in (68, 118, 300, 346):
        cx = X + f * hx * s
        tint(ic, ic.mask("ellipse", (cx - 40 * s, G - 10 * s, cx + 40 * s, G + 14 * s)), None, (10, 6, 2), 0.55, 5)

    near_fore = [(22, 352), (104, 340), (94, 280), (84, 210), (90, 184), (80, 158), (74, 50), (86, 18), (100, 0),
                 (38, 0), (46, 18), (50, 50), (48, 158), (38, 184), (44, 210), (34, 280)]
    near_hind = [(276, 368), (386, 368), (392, 300), (376, 236), (362, 196), (368, 168), (358, 148), (352, 50),
                 (362, 18), (376, 0), (316, 0), (322, 18), (328, 50), (328, 148), (318, 176), (302, 236), (288, 300)]
    far = union(ic.poly_mask(P(shift(near_fore, 52))), ic.poly_mask(P(shift(near_hind, -48))))
    ic.fill(far, tone(coat[0], 0.55), tone(coat[1], 0.5), (G - 360 * s, G), noise=0.16)
    tint(ic, ic.mask("rectangle", (0, G - 30 * s, SIZE, G + 4)), far, (20, 14, 8), 0.6)
    rim(ic, far, 3, (20, 12, 6), 0.6)

    # tail
    tl, _, _ = tube(P([(390, 430), (404, 370), (408, 310), (404, 262)]), [20 * s, 15 * s, 11 * s, 10 * s])
    ic.fill(ic.poly_mask(tl), tone(coat[0], 0.8), tone(coat[1], 0.8), noise=0.18)
    ic.fill(ic.poly_mask(P(ic.jitter(404, 250, 12, 26, 9, 0.25))), "#4a3220", "#1e140a", noise=0.2)

    body = [(10, 340), (-6, 392), (6, 444), (52, 470), (110, 480), (160, 522), (206, 558), (252, 542), (300, 484),
            (348, 462), (388, 430), (398, 384), (384, 340), (330, 310), (210, 300), (100, 306), (40, 318)]
    nk, _, _ = tube(P([(60, 420), (0, 382), (-60, 362), (-112, 382), (-146, 440), (-156, 518)]),
                    [150 * s, 100 * s, 78 * s, 68 * s, 64 * s, 60 * s])
    head = [(-126, 560), (-148, 592), (-196, 594), (-238, 578), (-272, 556), (-292, 530), (-288, 506), (-262, 494),
            (-226, 498), (-190, 506), (-156, 508), (-134, 520)]
    legs = union(ic.poly_mask(P(near_fore)), ic.poly_mask(P(near_hind)))
    mass = smooth(union(ic.poly_mask(P(body)), ic.poly_mask(nk), legs, ic.mask("ellipse", box(-10, 300, 130, 470)),
                        ic.mask("ellipse", box(250, 330, 400, 470))), 8 * s)
    hm = smooth(ic.poly_mask(P(head)), 5 * s)
    whole = union(mass, hm)
    xs = [p[0] for p in P(body + head)]
    ic.fill(whole, coat[0], coat[1], radial=(min(xs) + 80 * s, G - 640 * s, 760 * s), noise=0.18, chroma=0.06)
    modelled(ic, whole, s, (255, 226, 176), 0.42, 0.5)
    # volumes: belly and legs in shade, hump and shoulder lit, the thin legs darker below the knee
    tint(ic, ic.mask("ellipse", box(0, 250, 400, 360)), whole, (16, 10, 4), 0.35, 16 * s)
    tint(ic, ic.mask("ellipse", box(130, 470, 280, 570)), whole, (255, 236, 200), 0.18, 14 * s)
    tint(ic, ic.mask("rectangle", (0, G - 170 * s, SIZE, G)), legs, (30, 18, 8), 0.25, 10 * s)
    for leg in (near_fore, near_hind):
        lm = ic.intersect(ic.poly_mask(P(leg)), whole)
        tint(ic, ImageChops.subtract(lm, ImageChops.offset(lm, -int(12 * s) * f, 0)),
             ic.intersect(lm, ic.mask("rectangle", (0, G - 300 * s, SIZE, G))), (10, 6, 2), 0.4, 4 * s)
    for kx, ky in ((64, 172), (344, 158)):  # knee callosities
        ic.fill(ic.intersect(ic.mask("ellipse", box(kx - 22, ky - 16, kx + 22, ky + 16)), whole), "#6e5438", "#3a2814",
                noise=0.2)
    for hx in (68, 346):  # broad pads
        ic.fill(ic.intersect(whole, ic.mask("rectangle", (0, G - 18 * s, SIZE, G + 2))), "#5a4430", "#2a1e12",
                noise=0.12)
    hair(ic, whole, box(-290, 280, 400, 600), int(700 * s * s), 10 * s, alpha=34)
    # head: long face, heavy brow, drooping lip, small ear, halter
    tint(ic, ic.poly_mask(P([(-190, 506), (-262, 494), (-290, 510), (-270, 530), (-200, 520)])), hm, (20, 10, 4), 0.35,
         5 * s)
    tint(ic, ic.poly_mask(P([(-140, 590), (-200, 596), (-240, 578), (-200, 570), (-150, 572)])), hm, (255, 230, 186),
         0.3, 5 * s)
    ear = P([(-132, 582), (-122, 614), (-108, 610), (-112, 580)])
    ic.poly(ear, tone(coat[0], 0.9), tone(coat[1], 0.9), edge=3)
    ex, ey = P([(-176, 566)])[0]
    ic.draw.ellipse((ex - 6, ey - 4, ex + 6, ey + 4), fill=(18, 12, 10, 255))
    ic.line(P([(-192, 576), (-178, 576), (-164, 570)]), 3, (40, 26, 14, 170))  # heavy lid
    nx, ny = P([(-278, 530)])[0]
    ic.line([(nx - 4, ny - 2), (nx + 6 * f, ny + 2)], 4, (30, 18, 10, 220))
    ic.line(P([(-286, 506), (-262, 500)]), 3, (40, 24, 12, 180))  # lip
    ic.line(P([(-160, 510), (-150, 560), (-140, 586)]), 6, (70, 40, 24))  # halter
    ic.line(P([(-262, 520), (-158, 540)]), 6, (70, 40, 24))
    ic.line(P([(-220, 508), (-232, 470), (-240, 420)]), 5, (60, 40, 24))  # lead rope hanging
    rim(ic, whole, 4, (40, 22, 8), 0.6)

    if load == "bales":
        # striped kilim saddle cloth
        cloth = P([(96, 470), (330, 472), (340, 344), (300, 330), (130, 330), (90, 344)])
        cm = ic.poly_mask(cloth)
        ic.fill(cm, "#b43c2a", "#541810", (G - 472 * s, G - 330 * s), noise=0.16)
        stripes = [(0.2, (222, 180, 90, 230)), (0.36, (40, 52, 96, 230)), (0.64, (222, 180, 90, 230)),
                   (0.8, (40, 52, 96, 200))]

        def kilim(d):
            for fy, col in stripes:
                y = 330 + 140 * fy
                d.line(P([(80, y), (350, y)]), fill=col, width=max(4, int(12 * s)))
            for x in range(100, 340, 22):  # fringe
                d.line(P([(x, 334), (x + 2, 314)]), fill=(222, 196, 140, 220), width=3)

        ic.overlay(kilim, union(cm, ic.mask("rectangle", box(90, 300, 340, 334))))
        tint(ic, cm, None, (0, 0, 0), 0.12)
        ic.outline(cloth, 4, (40, 16, 10, 180))
        # the near bale (a far one peeks above the hump) and a rolled carpet on top
        far_b = P([(150, 560), (160, 600), (290, 600), (300, 556)])
        ic.fill(ic.poly_mask(far_b), "#8e7a58", "#4e402a", noise=0.18)
        ic.outline(far_b, 3, (40, 30, 18, 180))
        bb = box(128, 360, 316, 576)
        bm = ic.mask("rounded_rectangle", bb, radius=int(40 * s))
        ic.fill(bm, "#cbb48a", "#66533a", radial=(bb[0] if f > 0 else bb[2], bb[1], 300 * s), noise=0.18)
        tint(ic, ic.mask("rectangle", box(250 if f > 0 else 128, 360, 316 if f > 0 else 190, 576)), bm, (20, 12, 4),
             0.3, 14 * s)
        tint(ic, ic.mask("rectangle", box(128, 360, 316, 400)), bm, (20, 12, 4), 0.35, 10 * s)
        for fx in (0.3, 0.72):
            x = 128 + 188 * fx
            rope(ic, P([(x, 576), (x + 4, 470), (x, 362)]), 5, (140, 108, 64))
        rope(ic, P([(128, 470), (222, 474), (316, 468)]), 5, (140, 108, 64))
        ic.overlay(lambda d: d.rounded_rectangle(bb, radius=int(40 * s), outline=(50, 36, 20, 190), width=4))
        roll, _, _ = tube(P([(96, 596), (220, 610), (344, 600)]), [56 * s, 62 * s, 56 * s])
        rmk = ic.poly_mask(roll)
        ic.fill(rmk, "#9a3a2c", "#3e140e", (G - 640 * s, G - 570 * s), noise=0.16)
        ic.overlay(lambda d: [d.line(P([(x, 574), (x + 6, 636)]), fill=(214, 176, 96, 200), width=max(3, int(8 * s)))
                              for x in (130, 190, 250, 310)], rmk)
        ends = [P([(96, 596)])[0], P([(344, 600)])[0]]
        for ex_, ey_ in ends:
            r = 29 * s
            ic.ellipse((ex_ - r * 0.55, ey_ - r, ex_ + r * 0.55, ey_ + r), "#c0806a", "#6a2a1e", edge=3)
            ic.overlay(lambda d, ex_=ex_, ey_=ey_, r=r: d.ellipse((ex_ - r * 0.25, ey_ - r * 0.5, ex_ + r * 0.25,
                                                                   ey_ + r * 0.5), outline=(60, 20, 12, 200), width=3))
        ic.outline(roll, 4, (40, 14, 8, 190))
    elif load == "salt":
        # goatskins at the shoulder, two lashed slabs of rock salt
        skin = P(ic.jitter(96, 400, 40, 56, 12, 0.12))
        sm = ic.poly_mask(skin)
        ic.fill(sm, "#6a4a30", "#26180c", radial=(P([(70, 450)])[0][0], P([(70, 450)])[0][1], 90 * s), noise=0.2)
        ic.outline(skin, 3, (30, 18, 8, 190))
        rope(ic, P([(96, 452), (120, 480)]), 4, (120, 90, 56))
        slabs = [((110, 440), (338, 470), (330, 540), (104, 512)), ((120, 346), (344, 368), (338, 446), (114, 430))]
        for quad in slabs:
            q = P(list(quad))
            qm = ic.poly_mask(q)
            ic.fill(qm, "#eee6d4", "#9c9280", radial=(min(p[0] for p in q), min(p[1] for p in q), 300 * s), noise=0.2)
            ic.overlay(lambda d, q=q: [d.line([(q[0][0] + (q[1][0] - q[0][0]) * t, q[0][1] + (q[1][1] - q[0][1]) * t + 6),
                                               (q[3][0] + (q[2][0] - q[3][0]) * t, q[3][1] + (q[2][1] - q[3][1]) * t - 6)],
                                              fill=(120, 110, 96, 110), width=3) for t in (0.18, 0.47, 0.8)], qm)
            tint(ic, ic.mask("rectangle", (0, max(p[1] for p in q) - 20 * s, SIZE, SIZE)), qm, (40, 30, 20), 0.3, 6 * s)
            edge = ImageChops.subtract(qm, ImageChops.offset(qm, 0, int(10 * s)))
            tint(ic, edge, qm, (255, 255, 246), 0.5, 2)
            ic.outline(q, 4, (60, 48, 36, 200))
        for x in (150, 296):
            rope(ic, P([(x - 4, 350), (x, 440), (x + 4, 540)]), 5, (150, 112, 66))
        rope(ic, P([(112, 490), (230, 500), (336, 506)]), 5, (150, 112, 66))
    return whole


# ---------------------------------------------------------------- date palms
def frond(ic: Icon, base, deg: float, length: float, droop: float = 0.35, colors=LEAF, shade: float = 0.0) -> None:
    """Palm frond: arched spine with long thin leaflets on both sides, drooping towards the tip."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 26)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    m = Image.new("L", (SIZE, SIZE), 0)
    dm = ImageDraw.Draw(m)
    rnd = ic.random.uniform
    for i in range(3, len(spine)):
        t = ts[i]
        p = spine[i]
        q = spine[i - 1]
        dx, dy = p - q
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx / ln, dy / ln
        lf = length * 0.24 * math.sin(math.pi * min(t * 0.9 + 0.1, 1)) ** 0.6 * rnd(0.85, 1.1)
        for sgn in (1, -1):
            nx, ny = -uy * sgn, ux * sgn
            # leaflets sweep forward and hang down a little
            ex = p[0] + (nx * 0.75 + ux * 0.55) * lf
            ey = p[1] + (ny * 0.75 + uy * 0.55) * lf + lf * 0.35
            dm.line([tuple(p), (ex, ey)], fill=255, width=int(max(5, 11 * (1 - t * 0.5))))
    dm.line([tuple(p) for p in spine], fill=255, width=9)
    m = m.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: 255 if v > 110 else 0)
    xs = [p[0] for p in spine]
    ys = [p[1] for p in spine]
    ic.fill(m, colors[0], colors[1], radial=(min(xs) - 40, min(ys) - 60, length * 1.3), noise=0.3, chroma=0.12)
    tint(ic, ic.mask("rectangle", (0, max(ys) - length * 0.3, SIZE, SIZE)), m, (10, 20, 4), 0.3, 20)
    if shade:
        tint(ic, m, m, (10, 16, 4), shade)
    ic.line([tuple(p) for p in spine[:-4]], 4, (170, 170, 96, 90))
    rim(ic, m, 2, (20, 30, 8), 0.5)


def palm(ic: Icon, foot, crown, r: float, lean: float = 0.0) -> None:
    """Date palm: slim ringed trunk with a slight curve, fronds all round, date clusters under them."""
    (fx, fy), (cx, cy) = foot, crown
    mx, my = (fx + cx) / 2 + lean, (fy + cy) / 2
    path = [(fx + (mx - fx) * t * 2 if t < 0.5 else mx + (cx - mx) * (t - 0.5) * 2,
             fy + (my - fy) * t * 2 if t < 0.5 else my + (cy - my) * (t - 0.5) * 2) for t in np.linspace(0, 1, 9)]
    tr, a, b = tube(path, [52, 44, 40, 38])
    tm = ic.poly_mask(tr)
    ic.fill(tm, "#9a7a56", "#4a3620", (min(fx, cx) - 30, max(fx, cx) + 40), vertical=False, noise=0.22)

    def rings(d: ImageDraw.ImageDraw) -> None:
        for i in range(1, len(a)):
            if i % 2:
                continue
            d.line([a[i], b[i]], fill=(50, 34, 18, 150), width=5)
            d.line([(a[i][0], a[i][1] - 7), (b[i][0], b[i][1] - 7)], fill=(220, 190, 140, 70), width=3)

    ic.overlay(rings, tm)
    tint(ic, ImageChops.subtract(tm, ImageChops.offset(tm, -14, 0)), tm, (20, 10, 4), 0.45, 4)
    ic.outline(tr, 4, (40, 26, 14, 170))
    # back fronds (darker), dates, then front fronds
    for deg, ln, dr in ((-160, 0.9, 0.3), (-20, 0.95, 0.3), (-120, 0.7, 0.2), (-60, 0.75, 0.2)):
        frond(ic, (cx, cy), deg, r * ln, dr, shade=0.3)
    for k in range(3):
        dx = (-34, 0, 30)[k]
        for _ in range(9):
            x = cx + dx + ic.random.uniform(-14, 14)
            y = cy + 30 + ic.random.uniform(0, 34)
            ic.ellipse((x - 9, y - 8, x + 9, y + 8), "#d0802e", "#6e3010", edge=3)
    for deg, ln, dr in ((-168, 1.0, 0.8), (-12, 1.0, 0.8), (168, 0.8, 0.7), (12, 0.85, 0.7), (-132, 0.8, 0.75),
                        (-48, 0.85, 0.75), (-100, 0.55, 0.6), (-80, 0.5, 0.5)):
        frond(ic, (cx, cy), deg, r * ln, dr)


# ---------------------------------------------------------------- the station house
def house(ic: Icon) -> None:
    """Low red mud-brick house: rounded corners, rendered walls with smudges, toron beams, parapet."""
    x0, x1, top = 250, 640, 640
    annex = (130, 760, 300, BASE)
    for (a, t, b, bot), shade in ((annex, 0.12), ((x0, top, x1, BASE), 0.0)):
        m = ic.mask("rounded_rectangle", (a, t, b, bot + 30), radius=34)
        m = ic.intersect(m, ic.mask("rectangle", (0, 0, SIZE, bot)))
        # parapet with rounded merlons
        for x in np.arange(a + 14, b - 30, 62):
            m = union(m, ic.mask("rounded_rectangle", (x, t - 34, x + 36, t + 20), radius=14))
        ic.fill(m, MUD[0], MUD[1], (t - 34, bot), noise=0.24, chroma=0.06)
        for _ in range(26):  # render patches and wash marks
            x, y = ic.random.uniform(a, b), ic.random.uniform(t, bot)
            tint(ic, ic.mask("ellipse", (x - 30, y - 18, x + 30, y + 22)), m,
                 (255, 214, 170) if ic.random.random() < 0.5 else (60, 24, 8), 0.14, 10)
        tint(ic, ic.mask("rectangle", (b - 60, t - 40, b + 10, bot)), m, (40, 14, 2), 0.35, 20)  # turned side
        tint(ic, ic.mask("rectangle", (a - 10, t - 40, a + 40, bot)), m, (255, 220, 180), 0.16, 12)
        tint(ic, ic.mask("rectangle", (a, t + 10, b, t + 50)), m, (40, 14, 2), 0.3, 10)  # under the parapet
        tint(ic, ic.mask("rectangle", (a, bot - 60, b, bot)), m, (60, 30, 10), 0.3, 16)
        if shade:
            tint(ic, m, m, (30, 10, 0), shade)
        rim(ic, m, 4, (50, 20, 6), 0.7)
        # toron beams: palm-wood stubs through the wall
        for y in (t + 70, t + 150):
            for x in np.arange(a + 40, b - 30, 76):
                x += ic.random.uniform(-8, 8)
                ic.rect((x - 8, y - 6, x + 26, y + 8), "#8a6440", "#4a3018", edge=3)
                tint(ic, ic.mask("rectangle", (x - 4, y + 8, x + 30, y + 22)), m, (30, 10, 0), 0.4, 4)
    # doorway with a palm-wood lintel and a hanging mat
    dx0, dx1, dy0 = 380, 470, 736
    dm = ic.mask("rounded_rectangle", (dx0, dy0, dx1, BASE + 20), radius=26)
    dm = ic.intersect(dm, ic.mask("rectangle", (0, 0, SIZE, BASE)))
    ic.fill(dm, "#2e1c10", "#120a04", (dy0, BASE), noise=0.1)
    mat = [(dx0 + 6, dy0 + 20), (dx1 - 6, dy0 + 20), (dx1 - 10, dy0 + 96), (dx0 + 10, dy0 + 90)]
    ic.fill(ic.poly_mask(mat), "#c4a060", "#7a5a30", noise=0.2)
    ic.overlay(lambda d: [d.line([(dx0 + 8, y), (dx1 - 8, y)], fill=(120, 40, 20, 200), width=5) for y in (dy0 + 40, dy0 + 70)],
               ic.poly_mask(mat))
    ic.outline(mat, 3)
    timber_pts = [(dx0 - 26, dy0 - 18), (dx1 + 26, dy0 - 18), (dx1 + 26, dy0 + 2), (dx0 - 26, dy0 + 2)]
    ic.poly(timber_pts, "#9a7248", "#5a3c20", edge=4)
    for wx in (300, 560):
        ic.rect((wx, 700, wx + 34, 744), "#2a1a0e", "#120a04", noise=0.08, edge=3)
        ic.line([(wx - 6, 698), (wx + 40, 698)], 8, (120, 80, 44))
    # triangular vents in the parapet, a Saharan motif
    for x in (330, 450, 570):
        ic.poly([(x - 14, top - 4), (x + 14, top - 4), (x, top - 24)], "#3a200e", "#1a0c04", edge=0)


def well(ic: Icon) -> None:
    """Stone-kerbed well, palm-trunk frame with a crossbar and pulley, a leather bucket on the rope."""
    x0, x1, top, bot = 36, 226, 816, 930
    cx = (x0 + x1) / 2
    for px, lean in ((x0 + 18, -6), (x1 - 18, 6)):
        ic.line([(px, bot - 30), (px + lean, 606)], 30, (60, 40, 22))
        ic.line([(px, bot - 30), (px + lean, 606)], 22, (150, 112, 70))
        ic.line([(px - 5, bot - 30), (px - 5 + lean, 606)], 5, (200, 170, 120, 120))
        ic.line([(px + lean - 18, 590), (px + lean, 614), (px + lean + 18, 590)], 12, (120, 86, 52))
    ic.line([(x0 - 8, 604), (x1 + 8, 604)], 22, (60, 40, 22))
    ic.line([(x0 - 8, 604), (x1 + 8, 604)], 14, (160, 120, 76))
    ic.ellipse((cx - 30, 596, cx + 30, 656), "#8a6440", "#3e2814", edge=4)
    ic.draw.ellipse((cx - 8, 618, cx + 8, 634), fill=(40, 30, 20, 255))
    rope(ic, [(cx + 26, 630), (cx + 28, 720)], 4, (170, 140, 96))
    bucket = [(cx + 2, 720), (cx + 54, 720), (cx + 46, 780), (cx + 10, 780)]
    ic.poly(bucket, "#7a4a2a", "#3a200e", edge=4)
    ic.overlay(lambda d: d.arc((cx + 4, 700, cx + 52, 740), 180, 360, fill=(60, 40, 22, 255), width=4))
    body = union(ic.mask("rectangle", (x0, top + 20, x1, bot)), ic.mask("ellipse", (x0, bot - 24, x1, bot + 24)))
    stones(ic, (x0, top, x1, bot + 24), "#c4a47a", "#7a5e3e", course=30, clip=body, lit=50, shadow=100)
    tint(ic, ic.mask("rectangle", (cx + 30, top, x1 + 10, bot + 30)), body, (30, 14, 4), 0.35, 16)
    ring = ic.mask("ellipse", (x0 - 4, top - 6, x1 + 4, top + 46))
    ic.fill(ring, "#d8bc92", "#8e6e48", (top, top + 46), noise=0.18)
    mouth = ic.mask("ellipse", (x0 + 22, top + 6, x1 - 22, top + 36))
    ic.fill(mouth, "#1e140a", "#3a2a1a", (top, top + 36), noise=0.08)
    ic.overlay(lambda d: d.arc((x0 + 30, top + 12, x1 - 30, top + 34), 20, 160, fill=(120, 150, 150, 120), width=4))
    ic.overlay(lambda d: d.ellipse((x0 - 4, top - 6, x1 + 4, top + 46), outline=(60, 40, 22, 200), width=4))
    ic.overlay(lambda d: d.line([(x0, top + 20), (x0, bot)], fill=(50, 34, 20, 200), width=5))
    ic.overlay(lambda d: d.line([(x1, top + 20), (x1, bot)], fill=(50, 34, 20, 200), width=5))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.84
    ic.grade["gamma"] = 0.74
    palm(ic, (560, 700), (596, 250), 190, lean=-20)
    palm(ic, (220, 780), (188, 150), 210, lean=24)
    house(ic)
    road(ic, BASE - 8, 978, c=("#dcb67c", "#9e7644"))
    tint(ic, ic.mask("ellipse", (520, GROUND - 26, 1010, GROUND + 26)), None, (0, 0, 0), 0.4, 14)
    well(ic)
    camel(ic, 734, GROUND, 0.74, load="salt", coat=("#bc8a54", "#46280e"))
