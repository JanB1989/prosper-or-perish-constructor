"""Camel Stud (camel_stud): the walled breeding yard of a court or a great caravan house.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/camel_stud/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/camel_stud

Identity (upgrade of camel_herders, whose icon is a goat-hair tent with a cow camel and her calf):
the herd moves behind walls. A long crenellated mud-brick yard wall with rounded corner buttresses and
toron beams, a gate tower with a pointed gateway and one door leaf swung open, date palms and a stack
of lucerne hay above the wall. In front the two strains the stud breeds: a big dark shaggy baggage
hybrid and a pale riding dromedary in a fringed saddle cloth, forked wooden saddle and tasselled
neck band.

Helpers: the caravan family's (see camel_herders), ``pointed`` (pp_caravanserai), ``frond`` and ``palm``
(pp_oasis_caravan_station), ``hay`` (stud_farm, greener); new: ``mud``, ``merlons``, ``yard_wall``,
``gate_tower``, ``riding_saddle``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 67
REFS = ("caravan_stop", "horse_breeders", "caravanserai", "trans_saharan_trade_outposts")

BASE = 890  # foot of the walls
GROUND = 944  # where the camels stand
WTOP = 610  # yard wall top
MUD = ("#cc935a", "#7e4c26")
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


def rope(ic: Icon, pts, width: int = 6, color=(176, 146, 100)) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, color)


def road(ic: Icon, top: float, bot: float, c=("#c9a878", "#8e7048"), x0: float = 16, x1: float = 1008) -> Image.Image:
    """Dusty ground band with pebbles, hoof marks and a shaded far edge; returns its mask."""
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def marks(d: ImageDraw.ImageDraw) -> None:
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
def camel(ic: Icon, X: float, G: float, s: float = 0.6, left: bool = True, load: str = "none",
          coat=("#cfa66c", "#5a3c20"), lead: bool = True) -> Image.Image:
    """Dromedary in profile standing on ``G``; head to the left unless ``left`` is False. ``load``:
    "none" (halter only). Local units, y up; returns the animal mask."""
    f = 1 if left else -1

    def P(pts):
        return [(X + f * x * s, G - y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def shift(pts, dx, dy=0):
        return [(x + dx, y + dy) for x, y in pts]

    for hx in (68, 118, 300, 346):  # hoof contact shadows
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
    tint(ic, ic.mask("ellipse", box(0, 250, 400, 360)), whole, (16, 10, 4), 0.35, 16 * s)
    tint(ic, ic.mask("ellipse", box(130, 470, 280, 570)), whole, (255, 236, 200), 0.22, 14 * s)  # the lit hump
    tint(ic, ic.mask("rectangle", (0, G - 170 * s, SIZE, G)), legs, (30, 18, 8), 0.25, 10 * s)
    for leg in (near_fore, near_hind):
        lm = ic.intersect(ic.poly_mask(P(leg)), whole)
        tint(ic, ImageChops.subtract(lm, ImageChops.offset(lm, -int(12 * s) * f, 0)),
             ic.intersect(lm, ic.mask("rectangle", (0, G - 300 * s, SIZE, G))), (10, 6, 2), 0.4, 4 * s)
    for kx, ky in ((64, 172), (344, 158)):  # knee callosities
        ic.fill(ic.intersect(ic.mask("ellipse", box(kx - 22, ky - 16, kx + 22, ky + 16)), whole), "#6e5438", "#3a2814",
                noise=0.2)
    ic.fill(ic.intersect(whole, ic.mask("rectangle", (0, G - 18 * s, SIZE, G + 2))), "#5a4430", "#2a1e12", noise=0.12)
    hair(ic, whole, box(-290, 280, 400, 600), int(700 * s * s), 10 * s, alpha=34)
    # head: long face, heavy brow, drooping lip, small ear, halter
    tint(ic, ic.poly_mask(P([(-190, 506), (-262, 494), (-290, 510), (-270, 530), (-200, 520)])), hm, (20, 10, 4), 0.35,
         5 * s)
    tint(ic, ic.poly_mask(P([(-140, 590), (-200, 596), (-240, 578), (-200, 570), (-150, 572)])), hm, (255, 230, 186),
         0.3, 5 * s)
    ear = P([(-132, 582), (-122, 614), (-108, 610), (-112, 580)])
    ic.poly(ear, tone(coat[0], 0.9), tone(coat[1], 0.9), edge=3)
    ex, ey = P([(-176, 566)])[0]
    ic.draw.ellipse((ex - 6 * s / 0.7, ey - 4 * s / 0.7, ex + 6 * s / 0.7, ey + 4 * s / 0.7), fill=(18, 12, 10, 255))
    ic.line(P([(-192, 576), (-178, 576), (-164, 570)]), 3, (40, 26, 14, 170))
    nx, ny = P([(-278, 530)])[0]
    ic.line([(nx - 4, ny - 2), (nx + 6 * f, ny + 2)], 4, (30, 18, 10, 220))
    ic.line(P([(-286, 506), (-262, 500)]), 3, (40, 24, 12, 180))
    if lead:
        ic.line(P([(-160, 510), (-150, 560), (-140, 586)]), max(3, int(8 * s)), (70, 40, 24))  # halter
        ic.line(P([(-262, 520), (-158, 540)]), max(3, int(8 * s)), (70, 40, 24))
        ic.line(P([(-220, 508), (-232, 470), (-240, 420)]), max(3, int(7 * s)), (60, 40, 24))
    rim(ic, whole, 4, (40, 22, 8), 0.6)
    return whole


def pointed(x0: float, x1: float, spring: float, bottom: float, k: float = 0.82, n: int = 18) -> list:
    """Two-centred pointed arch opening from ``bottom`` up to the springing line and the apex."""
    w = x1 - x0
    r = w * k
    mid = (x0 + x1) / 2
    th_mid = math.acos((mid - x0 - r) / r)
    left = [(x0 + r + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, th_mid, n)]
    right = [(x1 - (px - x0), py) for px, py in left[::-1]]
    return [(x0, bottom)] + left + right[1:] + [(x1, bottom)]


# ---------------------------------------------------------------- date palms (from pp_oasis_caravan_station)
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


# ---------------------------------------------------------------- the stud yard
def hay(ic: Icon, pts, strands: int = 260) -> Image.Image:
    """Loose fodder stack (lucerne hay): green-gold mass lit top-left, dark underside, straw strokes."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#c4a868", "#5e4a24", radial=(min(xs) + (max(xs) - min(xs)) * 0.3, min(ys), (max(ys) - min(ys)) * 1.4),
            noise=0.22)
    rnd = ic.random.uniform

    def straw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(strands):
            x, y = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
            a = rnd(-0.9, 0.9) + (math.pi if ic.random.random() < 0.5 else 0)
            ln = rnd(14, 40)
            t = rnd(-1, 1)
            col = (255, 240, 180, int(t * 110)) if t > 0 else (40, 34, 10, int(-t * 110))
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (min(xs), (min(ys) + max(ys)) / 2 + 10, max(xs), max(ys))), m, (30, 16, 4), 0.35, 16)
    rim(ic, m, 3, (40, 30, 10), 0.6)
    return m


def mud(ic: Icon, m: Image.Image, box, turned: float = 60) -> None:
    """Rendered mud brick: warm plaster with smudges and wash marks, lit left edge, shaded right edge."""
    a, t, b, bot = box
    ic.fill(m, MUD[0], MUD[1], (t, bot), noise=0.24, chroma=0.06)
    for _ in range(int((b - a) * (bot - t) / 5000) + 6):
        x, y = ic.random.uniform(a, b), ic.random.uniform(t, bot)
        tint(ic, ic.mask("ellipse", (x - 30, y - 18, x + 30, y + 22)), m,
             (255, 220, 180) if ic.random.random() < 0.5 else (70, 30, 10), 0.13, 10)
    if turned:
        tint(ic, ic.mask("rectangle", (b - turned, t - 60, b + 10, bot)), m, (40, 16, 4), 0.3, 18)
    tint(ic, ic.mask("rectangle", (a - 10, t - 60, a + 36, bot)), m, (255, 226, 186), 0.15, 12)
    tint(ic, ic.mask("rectangle", (a, bot - 60, b, bot)), m, (60, 30, 10), 0.3, 16)


def merlons(m: Image.Image, ic: Icon, a: float, b: float, top: float, step: float = 62, w: float = 36) -> Image.Image:
    for x in np.arange(a + 12, b - w + 4, step):
        m = union(m, ic.mask("rounded_rectangle", (x, top - 32, x + w, top + 20), radius=14))
    return m


def yard_wall(ic: Icon) -> None:
    """Long crenellated mud-brick wall of the breeding yard with rounded corner buttresses."""
    m = ic.mask("rectangle", (60, WTOP, 964, BASE))
    m = merlons(m, ic, 60, 964, WTOP)
    for x0, x1 in ((34, 130), (894, 990)):
        bm = ic.mask("rounded_rectangle", (x0, WTOP - 70, x1, BASE + 30), radius=40)
        m = union(m, ic.intersect(bm, ic.mask("rectangle", (0, 0, SIZE, BASE))))
    mud(ic, m, (34, WTOP - 70, 990, BASE), turned=0)
    tint(ic, ic.mask("rectangle", (60, WTOP + 16, 964, WTOP + 56)), m, (40, 14, 2), 0.3, 10)
    for x0, x1 in ((34, 130), (894, 990)):  # buttresses round: lit left, shaded right
        tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, WTOP - 80, x1 + 10, BASE)),
             ic.mask("rounded_rectangle", (x0, WTOP - 70, x1, BASE + 30), radius=40), (40, 16, 4), 0.35, 12)
    for y in (WTOP + 90, WTOP + 170):  # toron beams
        for x in np.arange(170, 880, 92):
            if 290 < x < 530:
                continue
            x += ic.random.uniform(-8, 8)
            ic.rect((x - 8, y - 6, x + 24, y + 8), "#8a6440", "#4a3018", edge=3)
            tint(ic, ic.mask("rectangle", (x - 4, y + 8, x + 28, y + 22)), m, (30, 10, 0), 0.35, 4)
    rim(ic, m, 4, (50, 20, 6), 0.7)


def gate_tower(ic: Icon, x0: float, x1: float, top: float) -> None:
    """Gate tower with a pointed gateway, one leaf of the door swung open, a window and vents."""
    m = ic.mask("rectangle", (x0, top, x1, BASE))
    m = merlons(m, ic, x0 - 6, x1 + 6, top, step=50, w=32)
    mud(ic, m, (x0, top - 32, x1, BASE), turned=56)
    tint(ic, ic.mask("rectangle", (x0, top + 16, x1, top + 54)), m, (40, 14, 2), 0.3, 10)
    cx = (x0 + x1) / 2
    ring = pointed(x0 + 22, x1 - 22, 700, BASE)
    ic.fill(ic.poly_mask(ring), "#b8824e", "#6e4422", (600, BASE), noise=0.2)
    opening = pointed(x0 + 38, x1 - 38, 712, BASE)
    om = ic.poly_mask(opening)
    ic.fill(om, "#2e1c10", "#120a04", (600, BASE), noise=0.1)
    with ic.clipped(om):
        # the yard seen through the gate: sunlit ground and a far wall
        ic.fill(ic.mask("rectangle", (x0, BASE - 70, x1, BASE)), "#d6ae76", "#8a6438", noise=0.2)
        ic.fill(ic.mask("rectangle", (x0, 740, x1, BASE - 70)), "#a87648", "#5e3a1c", noise=0.2)
        tint(ic, ic.mask("rectangle", (x0, 600, x1, 780)), None, (0, 0, 0), 0.5, 20)
        # the left door leaf swung inwards, studded planks
        leaf = [(x0 + 38, 720), (x0 + 86, 740), (x0 + 86, BASE - 4), (x0 + 38, BASE)]
        lm = ic.poly_mask(leaf)
        ic.fill(lm, "#7a5030", "#3a2210", (700, BASE), noise=0.2)
        ic.overlay(lambda d: [d.line([(x, 724), (x, BASE)], fill=(30, 16, 6, 140), width=3)
                              for x in np.arange(x0 + 50, x0 + 86, 12)], lm)
        for y in (770, 840):
            ic.line([(x0 + 38, y), (x0 + 86, y + 6)], 6, (50, 46, 42))
    ic.outline(opening, 5)
    # a small barred window and triangular vents above the gate
    ic.rect((cx - 20, top + 80, cx + 20, top + 128), "#2a1a0e", "#120a04", noise=0.08, edge=3)
    ic.overlay(lambda d: [d.line([(x, top + 80), (x, top + 128)], fill=(110, 80, 50, 230), width=4)
                          for x in (cx - 8, cx + 8)])
    ic.line([(cx - 30, top + 76), (cx + 30, top + 76)], 8, (120, 80, 44))
    for x in (x0 + 36, x1 - 36):
        ic.poly([(x - 14, top + 40), (x + 14, top + 40), (x, top + 18)], "#3a200e", "#1a0c04", edge=0)
    for y in (top + 170,):
        for x in np.arange(x0 + 24, x1 - 20, 58):
            ic.rect((x - 8, y - 6, x + 22, y + 8), "#8a6440", "#4a3018", edge=3)
    rim(ic, m, 4, (50, 20, 6), 0.7)


def riding_saddle(ic: Icon, X: float, G: float, s: float, left: bool = True) -> None:
    """Riding gear for a camel drawn by ``camel`` with the same frame: a fringed saddle cloth over the
    hump, a wooden saddle with forked pommels and a sheepskin seat, a tasselled neck band."""
    f = 1 if left else -1

    def P(pts):
        return [(X + f * x * s, G - y * s) for x, y in pts]

    cloth = P([(104, 466), (112, 490), (140, 526), (172, 552), (206, 566), (248, 554), (290, 520), (326, 488),
               (334, 466)])
    cm = smooth(ic.poly_mask(cloth), 3)
    ic.fill(cm, "#b4382a", "#4e140c", (G - 570 * s, G - 466 * s), noise=0.16)

    def bands(d):
        for y, col in ((478, (226, 176, 72, 230)), (506, (30, 40, 90, 220))):
            d.line(P([(80, y), (350, y)]), fill=col, width=max(4, int(14 * s)))
        for x in np.arange(120, 320, 30):
            d.polygon(P([(x, 480), (x + 9, 492), (x, 504), (x - 9, 492)]), fill=(236, 220, 180, 230))

    ic.overlay(bands, cm)
    ic.outline(cloth, 4, (40, 14, 8, 190))
    for x in np.linspace(112, 326, 9):  # fringe and tassels
        px, py = P([(x, 468)])[0]
        ic.line([(px, py), (px + 2, py + 40 * s)], max(3, int(6 * s)), (230, 176, 60))
        ic.draw.ellipse((px - 7 * s, py + 34 * s, px + 9 * s, py + 52 * s), fill=(40, 52, 110, 255))
    # sheepskin seat and the two forked pommels of the saddle
    seat = P([(150, 566), (170, 588), (250, 584), (268, 564), (236, 556), (180, 558)])
    ic.fill(ic.poly_mask(seat), "#ece0c4", "#9a8a6a", noise=0.24)
    ic.outline(seat, 3, (60, 46, 30, 200))
    for x0, lean in ((142, -10), (272, 10)):
        post = P([(x0, 548), (x0 + lean, 632)])
        ic.line(post, max(6, int(16 * s)), (60, 36, 18))
        ic.line(post, max(4, int(10 * s)), (156, 108, 62))
        fork_a = P([(x0 + lean, 628), (x0 + lean - 14, 656)])
        fork_b = P([(x0 + lean, 628), (x0 + lean + 14, 656)])
        for fk in (fork_a, fork_b):
            ic.line(fk, max(4, int(10 * s)), (120, 80, 44))
    ic.line(P([(146, 604), (268, 604)]), max(4, int(10 * s)), (120, 80, 44))
    # neck band with tassels and shells
    band = P([(-60, 470), (-92, 440), (-118, 404)])
    ic.line(band, max(5, int(12 * s)), (180, 40, 30))
    for bx, by in band:
        ic.line([(bx, by), (bx, by + 30 * s)], max(3, int(6 * s)), (230, 176, 60))
        ic.draw.ellipse((bx - 6 * s, by + 26 * s, bx + 6 * s, by + 40 * s), fill=(236, 232, 220, 255))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.8
    ic.grade["gamma"] = 0.72
    palm(ic, (210, 640), (186, 230), 190, lean=24)
    palm(ic, (800, 620), (836, 300), 170, lean=-20)
    hay(ic, [(590, 640), (604, 586), (650, 548), (720, 530), (790, 540), (846, 574), (870, 640)])
    yard_wall(ic)
    gate_tower(ic, 300, 520, 450)
    road(ic, BASE - 8, 978, c=("#dcb47a", "#9a7042"), x0=24, x1=1000)
    tint(ic, ic.mask("ellipse", (40, GROUND - 26, 1000, GROUND + 26)), None, (0, 0, 0), 0.4, 14)
    # the baggage hybrid: big, dark and shaggy; the pale riding camel in its saddle gear
    hm = camel(ic, 196, GROUND - 10, 0.52, coat=("#8a5c34", "#2a160a"))
    hair(ic, hm, (40, 600, 420, 900), 320, 16, light=(200, 160, 110), dark=(20, 10, 4), alpha=80)
    camel(ic, 700, GROUND, 0.68, coat=("#e4caa0", "#6e5030"))
    riding_saddle(ic, 700, GROUND, 0.68)
