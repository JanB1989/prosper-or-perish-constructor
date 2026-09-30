"""Caravanserai (pp_caravanserai): Persian/Ottoman fortified courtyard inn with its great iwan portal.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pp_caravanserai/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pp_caravanserai

Identity: a long, blind sandstone curtain wall with stepped merlons and two round corner towers
(the closed square of the courtyard inn), a tall rectangular pishtaq with a deep pointed iwan
arch framed in turquoise tile, and a laden dromedary on the dusty road in front (bales over a
striped kilim, a rolled carpet on top). Bales and sacks wait by the left tower.
Caravan-family helpers (shared by pp_caravanserai, pp_oasis_caravan_station, pp_yam_station,
pp_banjara_tanda, pp_llama_caravan_post): ``union``, ``tint``, ``paste_clipped``, ``rim``,
``stones``, ``sack``, ``rope`` (from carrier_inn), ``smooth``, ``tube``, ``hair`` (from cattle_farm),
new ``pointed`` (pointed-arch outline), ``modelled`` (lit back / dark belly on an animal mask),
``road``; local to this icon: ``camel``, ``tower``, ``pishtaq``, ``curtain``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 23
REFS = ("caravanserai", "caravan_stop", "trans_saharan_trade_outposts", "tambo")

BASE = 890  # foot of the walls
GROUND = 944  # where the camel stands
WTOP = 440  # curtain wall top
SAND = ("#e2b674", "#a0703a")
SAND_DARK = ("#b48e5a", "#6e5030")


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
    top) or "salt" (two lashed salt slabs on the flank, goatskins at the shoulder).
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


# ---------------------------------------------------------------- building parts
def curtain(ic: Icon) -> None:
    """The blind outer wall of the courtyard: coursed sandstone, stepped merlons, shallow niches."""
    x0, x1 = 120, 910
    merlons = []
    for x in np.arange(x0 + 10, x1 - 30, 64):
        merlons.append((x, x + 38))
    wm = ic.mask("rectangle", (x0, WTOP, x1, BASE))
    for a, b in merlons:
        wm = union(wm, ic.poly_mask([(a, WTOP), (a, WTOP - 22), (a + 8, WTOP - 22), (a + 8, WTOP - 40), (b - 8, WTOP - 40),
                                     (b - 8, WTOP - 22), (b, WTOP - 22), (b, WTOP)]))
    stones(ic, (x0, WTOP - 40, x1, BASE), SAND[0], SAND[1], course=34, clip=wm, lit=45, shadow=90)
    # parapet coping line and the shadow under it
    ic.rect((x0 - 6, WTOP - 4, x1 + 6, WTOP + 14), "#e2c28e", "#a4804e", edge=4)
    tint(ic, ic.mask("rectangle", (x0, WTOP + 14, x1, WTOP + 50)), wm, (40, 20, 6), 0.35, 10)
    # blind pointed niches (a shallow arcade along the wall)
    for cx in (540, 660, 780):
        pts = pointed(cx - 40, cx + 40, 600, 830)
        nm = ic.poly_mask(pts)
        ic.fill(nm, "#b48c58", "#7a5a34", (520, 830), noise=0.18)
        tint(ic, ic.mask("rectangle", (cx - 44, 500, cx - 20, 840)), nm, (30, 16, 6), 0.4, 6)  # inner left side
        tint(ic, ic.mask("rectangle", (cx - 44, 500, cx + 44, 590)), nm, (30, 16, 6), 0.35, 12)  # under the arch
        tint(ic, ic.mask("rectangle", (cx + 28, 560, cx + 44, 840)), nm, (255, 236, 196), 0.25, 3)  # lit reveal
        ic.outline(pts, 4, (60, 40, 20, 200))
        ic.rect((cx - 22, 660, cx + 22, 730), "#2a1e14", "#140c06", noise=0.08, edge=3)  # arrow slit / window
    tint(ic, ic.mask("rectangle", (x0, BASE - 70, x1, BASE)), wm, (60, 40, 18), 0.25, 20)  # dust splash
    ic.outline([(x0, WTOP), (x1, WTOP), (x1, BASE), (x0, BASE)], 5)


def tower(ic: Icon, x0: float, x1: float, top: float) -> None:
    """Round corner tower: cylinder shaded across, coursed stone, cornice band, merlons on the rim."""
    w = x1 - x0
    body = ic.mask("rectangle", (x0, top, x1, BASE))
    body = union(body, ic.mask("ellipse", (x0, BASE - w * 0.16, x1, BASE + w * 0.16)))
    stones(ic, (x0, top, x1, BASE + w * 0.16), SAND[0], SAND[1], course=32, clip=body, long=0.8, lit=45, shadow=90)
    # cylinder shading: lit band left of centre, dark right side
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top, x1 + 20, BASE + 40)), body, (30, 16, 6), 0.42, w * 0.18)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.18, top, x0 + w * 0.38, BASE)), body, (255, 240, 206), 0.2, w * 0.1)
    tint(ic, ic.mask("rectangle", (x0 - 10, top, x0 + w * 0.08, BASE + 40)), body, (30, 16, 6), 0.2, 8)
    # cornice band and the rim with merlons
    band = union(ic.mask("rectangle", (x0 - 10, top - 10, x1 + 10, top + 24)),
                 ic.mask("ellipse", (x0 - 10, top + 10, x1 + 10, top + 38)))
    ic.fill(band, "#e4c894", "#9a7646", (top - 10, top + 38), noise=0.16)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top - 20, x1 + 20, top + 40)), band, (30, 16, 6), 0.35, 10)
    tint(ic, ic.mask("rectangle", (x0 - 10, top + 38, x1 + 10, top + 70)), body, (30, 16, 6), 0.4, 8)
    ic.overlay(lambda d: d.chord((x0 - 10, top + 10, x1 + 10, top + 38), 0, 180, outline=(60, 40, 20, 200), width=4))
    for fx in (0.04, 0.36, 0.68):
        a, b = x0 + w * fx - 4, x0 + w * fx + w * 0.26
        mm = ic.mask("rectangle", (a, top - 44, b, top - 8))
        ic.fill(mm, "#dcbc86", "#9a7646", (top - 44, top), noise=0.16)
        if fx > 0.5:
            tint(ic, mm, mm, (30, 16, 6), 0.3)
        ic.outline([(a, top - 8), (a, top - 44), (b, top - 44), (b, top - 8)], 4, (60, 40, 20, 200))
    ic.rect((x0 + w * 0.42, top + 150, x0 + w * 0.58, top + 230), "#2a1e14", "#140c06", noise=0.08, edge=3)
    ic.outline([(x0 - 10, top - 10), (x1 + 10, top - 10), (x1 + 10, top + 24)], 4)
    ic.overlay(lambda d: d.line([(x0, top + 30), (x0, BASE)], fill=(40, 26, 14, 200), width=5))
    ic.overlay(lambda d: d.line([(x1, top + 30), (x1, BASE)], fill=(40, 26, 14, 200), width=5))


def pishtaq(ic: Icon, x0: float, x1: float, top: float) -> None:
    """The portal: a tall rectangular frame round a deep pointed iwan, turquoise tile band, door."""
    cx = (x0 + x1) / 2
    fm = ic.mask("rectangle", (x0, top, x1, BASE))
    stones(ic, (x0, top, x1, BASE), "#dcb880", "#9a7444", course=30, clip=fm, lit=60, shadow=110)
    tint(ic, ic.mask("rectangle", (x1 - 50, top, x1 + 10, BASE)), fm, (30, 16, 6), 0.3, 14)
    # parapet merlons on top
    for fx in np.linspace(0.02, 0.84, 5):
        a = x0 + (x1 - x0) * fx
        b = a + (x1 - x0) * 0.13
        ic.rect((a, top - 34, b, top + 2), "#dcbc86", "#9a7646", edge=4)
    ic.rect((x0 - 8, top - 4, x1 + 8, top + 14), "#e6c892", "#a4804e", edge=4)
    # turquoise tile frame (alfiz) and the arch opening
    ax0, ax1, spring = x0 + 46, x1 - 46, 488
    frame_out = ic.mask("rectangle", (x0 + 22, top + 38, x1 - 22, BASE))
    frame_in = ic.mask("rectangle", (x0 + 36, top + 52, x1 - 36, BASE))
    band = ImageChops.subtract(frame_out, frame_in)
    ic.fill(band, "#4aa4a4", "#1c5a64", (top, BASE), noise=0.22, chroma=0.06)
    ic.overlay(lambda d: [d.line([(x, top + 38), (x, top + 52)], fill=(236, 226, 190, 150), width=3)
                          for x in np.arange(x0 + 30, x1 - 22, 18)], band)
    # spandrels: lighter glazed panels with a lozenge hint
    span = ic.intersect(frame_in, ic.poly_mask([(x0, top), (x1, top), (x1, spring), (x0, spring)]))
    ic.fill(span, "#d8c29a", "#a88c60", (top, spring), noise=0.16)
    ic.overlay(lambda d: [d.polygon([(x, top + 110), (x + 20, top + 132), (x, top + 154), (x - 20, top + 132)],
                                    fill=(60, 130, 140, 170)) for x in (x0 + 84, x1 - 84)], span)
    ic.overlay(lambda d: d.rectangle((x0 + 36, top + 52, x1 - 36, BASE), outline=(60, 40, 20, 170), width=3))
    ring = pointed(ax0 - 16, ax1 + 16, spring, BASE)
    ic.fill(ic.poly_mask(ring), "#48a0a0", "#1a5460", (top, BASE), noise=0.2)
    opening = pointed(ax0, ax1, spring, BASE)
    om = ic.poly_mask(opening)
    ic.fill(om, "#6a4c2c", "#24170c", (top + 60, BASE), noise=0.14)
    with ic.clipped(om):
        # the iwan's half-vault: stepped muqarnas tiers catching light on their lower lips
        apex = min(p[1] for p in opening)
        for i, y in enumerate(np.arange(apex + 50, spring + 40, 34)):
            n = 3 + i
            w = (ax1 - ax0) * min(1, 0.35 + 0.18 * i)
            for k in range(n):
                cxk = cx - w / 2 + (k + 0.5) * w / n
                ic.overlay(lambda d, cxk=cxk, y=y, r=w / n / 2: d.arc((cxk - r, y - 18, cxk + r, y + 18), 0, 180,
                                                                     fill=(214, 176, 120, 40), width=4))
        # back wall of the iwan with the courtyard door
        bw = ic.mask("rectangle", (ax0, spring + 30, ax1, BASE))
        ic.fill(bw, "#8e6c44", "#4e3820", (spring, BASE), noise=0.18)
        dpts = pointed(cx - 50, cx + 50, 700, BASE - 2, k=0.75)
        dm = ic.poly_mask(dpts)
        ic.fill(dm, "#7a5230", "#3c2412", (650, BASE), noise=0.18)
        ic.overlay(lambda d: [d.line([(x, 640), (x, BASE)], fill=(40, 24, 10, 150), width=4)
                              for x in np.arange(cx - 30, cx + 40, 22)], dm)
        for y in (736, 820):
            ic.line([(cx - 50, y), (cx + 50, y)], 7, (48, 44, 40))
        ic.outline(dpts, 4, (40, 24, 10, 200))
        ic.draw.ellipse((cx + 22, 790, cx + 34, 802), fill=(150, 130, 70, 255))
        # side walls of the recess: the left one in deep shade, the right one catching light
        ic.fill(ic.poly_mask([(ax0, spring - 40), (ax0 + 40, spring + 40), (ax0 + 40, BASE - 30), (ax0, BASE)]),
                "#3a2816", "#1e140a", noise=0.12)
        ic.fill(ic.poly_mask([(ax1, spring - 40), (ax1 - 40, spring + 40), (ax1 - 40, BASE - 30), (ax1, BASE)]),
                "#b08656", "#6e5030", noise=0.16)
        ic.fill(ic.mask("rectangle", (ax0, BASE - 30, ax1, BASE)), "#6a5236", "#3e2e1c", noise=0.2)
        tint(ic, ic.mask("rectangle", (ax0, apex, ax1, spring + 60)), None, (0, 0, 0), 0.35, 30)
    ic.outline(opening, 5)
    ic.outline([(x0, top), (x1, top), (x1, BASE), (x0, BASE)], 5)


def goods(ic: Icon) -> None:
    """Bales and sacks waiting by the left tower."""
    for x0, y0, x1, y1, c in ((70, 800, 190, 902, ("#bca27a", "#5e4c34")), (150, 830, 262, 912, ("#a88a62", "#50402a"))):
        m = ic.mask("rounded_rectangle", (x0, y0, x1, y1), radius=18)
        ic.fill(m, c[0], c[1], radial=(x0, y0, (x1 - x0) * 1.6), noise=0.18)
        tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, y0, x1 + 10, y1)), m, (20, 12, 4), 0.3, 10)
        for fx in (0.33, 0.7):
            rope(ic, [(x0 + (x1 - x0) * fx, y0 + 2), (x0 + (x1 - x0) * fx + 3, y1 - 2)], 4, (130, 100, 60))
        rope(ic, [(x0 + 2, (y0 + y1) / 2), (x1 - 2, (y0 + y1) / 2 + 4)], 4, (130, 100, 60))
        ic.overlay(lambda d, b=(x0, y0, x1, y1): d.rounded_rectangle(b, radius=18, outline=(50, 36, 20, 190), width=4))
    sack(ic, 44, 930, 60, 70, c=("#d2c09a", "#7a6a4c"), lean=-0.2)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95
    ic.grade["gamma"] = 0.76
    curtain(ic)
    tower(ic, 24, 156, 392)
    tower(ic, 868, 1000, 392)
    pishtaq(ic, 206, 446, 176)
    road(ic, BASE - 8, 976, c=("#cfa872", "#8e6a3e"))
    tint(ic, ic.mask("ellipse", (470, GROUND - 26, 1010, GROUND + 26)), None, (0, 0, 0), 0.4, 14)
    goods(ic)
    camel(ic, 700, GROUND, 0.78, load="bales", coat=("#b27a44", "#402410"))
