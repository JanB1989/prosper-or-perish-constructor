"""Yam Station (pp_yam_station): Russian/Mongol relay post station in winter.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pp_yam_station/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pp_yam_station

Identity: a log post house under a snow-laden roof, its windows in carved white-and-blue frames,
a plank-fenced yard with a roofed gate, and a fresh post horse under a red painted duga with a
bell, harnessed to a loaded sledge on the snow; a striped verst post marks the post road. Snow,
logs and the duga keep it apart from the Carrier Inn (tiles, covered wagon, packhorse).
Caravan-family helpers copied from pp_caravanserai (see there); ``horse`` adapted from the tow
horse in river_boatmen_yard (duga and bell added); local: ``logs``, ``nalichnik``, ``roof``,
``fence``, ``sledge``, ``verst``, ``snowfield``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("pomor_outpost", "caravan_stop", "tambo", "market_village")

BASE = 890
GROUND = 944
HX0, HX1, EAVE, RIDGE = 40, 480, 492, 262  # post house
SNOW = ("#f4f6f8", "#9eaabc")
LOG = ("#9a6e44", "#3e2814")


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


# ---------------------------------------------------------------- post horse (tow horse from river_boatmen_yard)
def horse(ic: Icon, X: float, G: float, s: float = 1.0, bend: float = 0.12) -> tuple[float, float]:
    """Bay post horse in profile facing left, leaning into a padded collar under a painted duga (the
    Russian shaft bow) with a bell; lit from the upper left. Returns the shaft point at the collar."""

    def sm(t: float) -> float:
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def turn(x: float, y: float) -> tuple[float, float]:
        w = sm((130 - x) / 90) * sm((y - 230) / 60)
        a = bend * w
        dx, dy = x - 130, y - 290
        return 130 + dx * math.cos(a) - dy * math.sin(a), 290 + dx * math.sin(a) + dy * math.cos(a)

    def P(pts):
        out = []
        for x, y in pts:
            u, v = turn(x, y)
            out.append((X + u * s, G - v * s))
        return out

    for hx, hw in ((40, 42), (122, 38), (268, 40), (320, 40)):
        cx = X + (hx + hw / 2) * s
        tint(ic, ic.mask("ellipse", (cx - 34 * s, G - 8 * s, cx + 34 * s, G + 12 * s)), None, (10, 6, 2), 0.6, 5)
    # legs staggered in the pull: near fore reaching, near hind driving back
    far_fore = P([(100, 200), (112, 120), (122, 64), (124, 26), (122, 0), (160, 0), (154, 24), (150, 64), (146, 120),
                  (156, 200)])
    far_hind = P([(262, 200), (270, 140), (284, 92), (282, 40), (276, 22), (268, 0), (308, 0), (306, 22), (310, 40),
                  (316, 96), (330, 124), (338, 170), (330, 215)])
    for leg in (far_fore, far_hind):
        m = ic.poly_mask(leg)
        ic.fill(m, "#4a2e1c", "#160c06", (G - 200 * s, G), noise=0.14)
        rim(ic, m, 3, (14, 8, 4), 0.6)
    tail = P([(372, 262), (394, 250), (408, 190), (404, 120), (396, 92), (380, 110), (376, 176), (364, 232)])
    ic.fill(ic.poly_mask(tail), "#3a2418", "#120a06", (G - 262 * s, G - 92 * s), noise=0.2)
    ic.overlay(lambda d: [d.line([P([(380 + i * 6, 240)])[0], P([(384 + i * 6, 110 + i * 8)])[0]],
                                 fill=(110, 76, 48, 120), width=3) for i in range(4)])
    body = P([(44, 215), (52, 185), (90, 168), (180, 158), (260, 166), (300, 184), (330, 190), (370, 215), (384, 248),
              (372, 272), (330, 286), (250, 272), (170, 274), (126, 290), (96, 322), (64, 362), (40, 390), (26, 398),
              (8, 394), (-10, 370), (-30, 330), (-46, 298), (-54, 282), (-46, 268), (-24, 268), (-4, 282), (14, 300),
              (34, 298), (50, 270)])
    near_fore = P([(56, 206), (58, 120), (54, 64), (46, 26), (36, 0), (78, 0), (82, 24), (86, 64), (100, 120),
                   (122, 200)])
    near_hind = P([(290, 200), (300, 140), (322, 94), (328, 40), (326, 22), (322, 0), (362, 0), (358, 22), (356, 40),
                   (356, 96), (364, 124), (374, 170), (366, 220)])
    bm = union(ic.poly_mask(body), ic.poly_mask(near_fore), ic.poly_mask(near_hind))
    xs = [p[0] for p in body]
    ic.fill(bm, "#a8683a", "#3a1c0a", radial=(min(xs) + 60 * s, G - 420 * s, 480 * s), noise=0.14)
    lit = ImageChops.subtract(bm, ImageChops.offset(bm, int(12 * s), int(26 * s)))
    tint(ic, lit, bm, (255, 208, 150), 0.42, 7 * s)
    under = ImageChops.subtract(bm, ImageChops.offset(bm, int(-6 * s), int(-30 * s)))
    tint(ic, under, bm, (12, 6, 2), 0.5, 10 * s)
    tint(ic, ic.mask("rectangle", (X, G - 196 * s, X + 400 * s, G)), bm, (10, 4, 0), 0.3, 16 * s)
    tint(ic, ic.mask("ellipse", tuple(P([(276, 282)])[0]) + tuple(P([(356, 206)])[0])), bm, (255, 214, 170), 0.26, 12)
    tint(ic, ic.mask("ellipse", (X + 150 * s, G - 250 * s, X + 300 * s, G - 150 * s)), bm, (10, 4, 0), 0.25, 16)
    tint(ic, ic.mask("rectangle", (X, G - 70 * s, X + 400 * s, G)), bm, (20, 12, 8), 0.7, 6)
    for hx in (36, 322):
        ic.fill(ic.intersect(bm, ic.mask("rectangle", (X + hx * s - 8, G - 16 * s, X + (hx + 44) * s, G + 2))),
                "#4a3e34", "#1a140e", noise=0.1)
    rim(ic, bm, 3, (30, 14, 6), 0.7)
    mane = P([(128, 292), (98, 328), (66, 368), (40, 396), (30, 384), (54, 354), (84, 316), (114, 286)])
    ic.fill(ic.poly_mask(mane), "#2e1c12", "#0e0806", noise=0.2)
    ic.poly(P([(30, 398), (38, 428), (50, 400)]), "#9a643a", "#3a2214", edge=3)
    ex, ey = P([(4, 366)])[0]
    ic.draw.ellipse((ex - 5, ey - 4, ex + 5, ey + 4), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 4, ey - 3, ex - 1, ey - 1), fill=(190, 180, 170, 255))
    ic.line(P([(-34, 312), (-8, 330), (14, 356), (22, 388)]), 5, (60, 36, 22))  # bridle
    # back pad and belly band
    pad = P([(170, 284), (200, 290), (230, 284), (236, 250), (200, 244), (168, 250)])
    ic.fill(ic.poly_mask(pad), "#7a5434", "#34200f", (G - 290 * s, G - 244 * s), noise=0.12)
    ic.outline(pad, 3, (30, 18, 10, 200))
    ic.line(P([(202, 246), (200, 164)]), 8, (54, 34, 20))
    # padded collar: a thick leather ring round the neck base, lit along its upper-left edge
    cl = [(128, 322), (112, 300), (96, 270), (82, 240), (72, 214), (70, 194), (78, 182)]
    ctr = P(cl)
    half = 24 * s
    left, right = [], []
    for i, (px, py) in enumerate(ctr):
        qx, qy = ctr[min(i + 1, len(ctr) - 1)]
        rx, ry = ctr[max(i - 1, 0)]
        dx, dy = qx - rx, qy - ry
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = half * (0.55 + 0.45 * math.sin(math.pi * i / (len(ctr) - 1)))
        left.append((px + nx * w, py + ny * w))
        right.append((px - nx * w, py - ny * w))
    collar = left + right[::-1]
    km = ic.poly_mask(collar)
    ic.fill(km, "#6e4a2c", "#24160a", radial=(ctr[1][0] - 20 * s, ctr[1][1] - 30 * s, 150 * s), noise=0.12)
    edge = ImageChops.subtract(km, ImageChops.offset(km, int(8 * s), int(10 * s)))
    tint(ic, edge, km, (240, 196, 140), 0.55, 3)
    ic.outline(collar, 3, (26, 16, 8, 210))
    tint(ic, ImageChops.subtract(km, ImageChops.offset(km, int(-8 * s), int(-8 * s))), km, (10, 6, 2), 0.45, 3)
    ic.line([(p[0] + 8 * s, p[1] - 3 * s) for p in ctr[1:5]], max(3, int(6 * s)), (196, 168, 110))  # hames
    ic.line([(p[0] + 6 * s, p[1] - 6 * s) for p in ctr[1:5]], 2, (250, 232, 180, 170))
    # duga: a red painted bow from shaft to shaft over the collar, seen slightly turned, bell under the crown
    bow = [(62 + 34 * (1 - math.cos(a)), 200 + 290 * math.sin(a)) for a in np.linspace(0, math.pi, 24)]
    pts = [(X + x * s, G - y * s) for x, y in bow]
    ic.line(pts, max(10, int(30 * s)), (40, 14, 8))
    ic.line(pts, max(6, int(22 * s)), (178, 40, 30))
    ic.line([(x - 4 * s, y - 3 * s) for x, y in pts[:14]], max(2, int(6 * s)), (240, 150, 110, 150))
    for x, y in pts[3:-3:3]:
        ic.draw.ellipse((x - 5 * s, y - 5 * s, x + 5 * s, y + 5 * s), fill=(226, 184, 70, 255))
    bx, by = X + 96 * s, G - 452 * s
    ic.line([(bx, by - 26 * s), (bx, by)], 3, (60, 40, 20))
    bell = [(bx - 16 * s, by + 22 * s), (bx - 12 * s, by), (bx, by - 8 * s), (bx + 12 * s, by), (bx + 16 * s, by + 22 * s)]
    ic.poly(bell, "#e2bc5a", "#7a5418", edge=3)
    return P([(80, 206)])[0]



# ---------------------------------------------------------------- post house
def logs(ic: Icon, x0, x1, y0, y1, d: float = 36, ends: bool = True, clip: Image.Image | None = None) -> Image.Image:
    """Horizontal log wall: every log a lit-top cylinder with grain, moss chinking between, and the
    notched log ends standing out at the corners on alternate courses. Returns the wall mask."""
    m = ic.mask("rectangle", (x0, y0, x1, y1))
    if clip is not None:
        m = ic.intersect(m, clip)
    ic.fill(m, LOG[0], LOG[1], (y0, y1), noise=0.2)
    rnd = ic.random.uniform
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d_ = ImageDraw.Draw(lay)
    y = y1
    rows = []
    while y > y0:
        h = d * rnd(0.9, 1.1)
        top = y - h
        rows.append((top, y))
        d_.rectangle((x0, top, x1, top + h * 0.35), fill=(255, 226, 180, int(rnd(40, 70))))
        d_.rectangle((x0, top + h * 0.65, x1, y), fill=(20, 10, 4, int(rnd(60, 100))))
        for _ in range(int((x1 - x0) / 70)):
            gx = rnd(x0, x1)
            gy = top + rnd(h * 0.3, h * 0.7)
            d_.line([(gx, gy), (gx + rnd(40, 120), gy + rnd(-2, 2))], fill=(40, 24, 10, 70), width=2)
        d_.line([(x0, y - 2), (x1, y - 2)], fill=(70, 80, 50, 150), width=5)  # moss chinking
        d_.line([(x0, y - 5), (x1, y - 5)], fill=(20, 12, 6, 160), width=3)
        y = top
    paste_clipped(ic, lay, m)
    if ends:
        for i, (top, bot) in enumerate(rows):
            if i % 2:
                continue
            r = (bot - top) * 0.56
            cy = (top + bot) / 2
            for cx in (x0 - r * 0.5, x1 + r * 0.5):
                box = (cx - r, cy - r, cx + r, cy + r)
                ic.fill(ic.mask("ellipse", box), "#caa272", "#6e4a28", radial=(cx - r * 0.6, cy - r * 0.6, r * 2), noise=0.14)
                ic.overlay(lambda dd, cx=cx, cy=cy, r=r: [dd.ellipse((cx - r * f, cy - r * f, cx + r * f, cy + r * f),
                                                                       outline=(90, 60, 30, 110), width=2)
                                                           for f in (0.35, 0.65)])
                ic.overlay(lambda dd, box=box: dd.ellipse(box, outline=(40, 24, 12, 210), width=4))
    return m


def nalichnik(ic: Icon, x, y, w: float = 58, h: float = 76) -> None:
    """Window in a carved, painted surround: white frame with a peaked fretwork crown, blue shutters."""
    for sx in (-1, 1):  # shutters
        a = x - w / 2 - 34 if sx < 0 else x + w / 2 + 10
        ic.rect((a, y - 4, a + 24, y + h + 4), "#4a74a4", "#223c5e", edge=4)
        ic.line([(a + 4, y + h / 2), (a + 20, y + h / 2)], 4, (230, 226, 214))
    ic.rect((x - w / 2 - 12, y - 12, x + w / 2 + 12, y + h + 14), "#eeeae0", "#a8a49a", edge=4)
    crown = [(x - w / 2 - 20, y - 12), (x + w / 2 + 20, y - 12), (x + w / 2 + 8, y - 30), (x, y - 58),
             (x - w / 2 - 8, y - 30)]
    ic.poly(crown, "#eeeae0", "#aaa69c", edge=4)
    ic.poly([(x - 16, y - 20), (x + 16, y - 20), (x, y - 40)], "#4a74a4", "#223c5e", edge=0)
    ic.rect((x - w / 2 - 16, y + h + 12, x + w / 2 + 16, y + h + 24), "#e2ded2", "#9a968c", edge=4)
    ic.rect((x - w / 2, y, x + w / 2, y + h), "#3a3a42", "#16161c", noise=0.08, edge=0)
    ic.shade(ic.poly_mask([(x - w / 2, y), (x + w * 0.1, y), (x - w / 2, y + h * 0.5)]), (170, 186, 206), 0.2)
    ic.line([(x, y), (x, y + h)], 6, (230, 226, 214))
    ic.line([(x - w / 2, y + h * 0.42), (x + w / 2, y + h * 0.42)], 6, (230, 226, 214))
    # snow on the sill and the crown
    ic.fill(ic.mask("rounded_rectangle", (x - w / 2 - 18, y + h + 4, x + w / 2 + 18, y + h + 16), radius=6),
            SNOW[0], SNOW[1], noise=0.06)


def roof(ic: Icon) -> None:
    """Board roof buried in snow: a thick snow plane with a soft rolled edge, eave boards below."""
    pts = [(HX0 - 40, EAVE + 6), (HX0 + 30, RIDGE), (HX1 - 30, RIDGE - 4), (HX1 + 40, EAVE + 2)]
    # eave board and the shadow it throws
    ic.rect((HX0 - 40, EAVE - 4, HX1 + 40, EAVE + 26), "#6e4a2c", "#3a2414", edge=4)
    m = ic.poly_mask(pts)
    ic.fill(m, SNOW[0], SNOW[1], (RIDGE, EAVE), noise=0.07, chroma=0.03)
    tint(ic, ic.poly_mask([(HX0 + 30, RIDGE), (HX0 + 200, RIDGE), (HX0 + 60, EAVE), (HX0 - 40, EAVE)]), m,
         (255, 255, 255), 0.35, 30)
    tint(ic, ic.mask("rectangle", (HX1 - 120, RIDGE, HX1 + 60, EAVE)), m, (70, 90, 130), 0.18, 40)
    rnd = ic.random.uniform

    def drifts(d):
        for _ in range(14):  # wind ripples on the snow
            x, y = rnd(HX0, HX1), rnd(RIDGE + 30, EAVE - 30)
            d.arc((x - 50, y - 10, x + 50, y + 10), 200, 340, fill=(120, 136, 170, 70), width=4)
        for x in np.arange(HX0 + 60, HX1, 90):  # board ends showing through along the ridge
            d.line([(x, RIDGE + 2), (x + 6, RIDGE + 18)], fill=(90, 70, 50, 110), width=5)

    ic.overlay(drifts, m)
    # rolled snow edge hanging over the eave, lumpy
    edge = Image.new("L", (SIZE, SIZE), 0)
    de = ImageDraw.Draw(edge)
    x = HX0 - 46
    while x < HX1 + 46:
        r = rnd(22, 34)
        de.ellipse((x - r, EAVE - 12 - r * 0.6, x + r, EAVE - 6 + r * 0.7), fill=255)
        x += r * 1.2
    ic.fill(edge, SNOW[0], "#b4bece", (EAVE - 40, EAVE + 30), noise=0.06)
    tint(ic, ic.mask("rectangle", (0, EAVE + 4, SIZE, EAVE + 40)), edge, (60, 80, 120), 0.35, 8)
    for x in (130, 300, 410):  # icicles
        ic.poly([(x - 7, EAVE + 16), (x + 7, EAVE + 16), (x, EAVE + 16 + rnd(26, 44))], "#e6eef6", "#9cb0c8", edge=3)
    ic.outline(pts, 6)
    # the ridge board and a chimney with a snow cap and a thread of smoke
    cx0, cx1, ctop = 330, 384, 180
    ic.rect((cx0, ctop, cx1, RIDGE + 30), "#9a5e44", "#5a3222", edge=4)
    ic.overlay(lambda d: [d.line([(cx0, y), (cx1, y)], fill=(60, 30, 20, 120), width=3) for y in range(ctop + 20, RIDGE + 30, 18)])
    ic.fill(ic.mask("rounded_rectangle", (cx0 - 12, ctop - 18, cx1 + 12, ctop + 10), radius=10), SNOW[0], SNOW[1],
            noise=0.06)
    ic.overlay(lambda d: d.rounded_rectangle((cx0 - 12, ctop - 18, cx1 + 12, ctop + 10), radius=10,
                                             outline=(40, 30, 30, 200), width=4))


def house(ic: Icon) -> None:
    wall = logs(ic, HX0, HX1, EAVE + 20, BASE, d=38)
    tint(ic, ic.mask("rectangle", (HX0, EAVE + 20, HX1, EAVE + 80)), wall, (0, 0, 0), 0.45, 14)
    tint(ic, ic.mask("rectangle", (HX1 - 60, EAVE, HX1, BASE)), wall, (0, 0, 0), 0.25, 20)
    ic.outline([(HX0, EAVE + 20), (HX1, EAVE + 20), (HX1, BASE), (HX0, BASE)], 5)
    for x in (120, 272):
        nalichnik(ic, x, 590)
    # plank door with a small porch roof
    dx0, dx1 = 372, 446
    ic.rect((dx0 - 10, 640, dx1 + 10, BASE), "#6e4a2c", "#3a2414", edge=4)
    ic.rect((dx0, 652, dx1, BASE), "#8a6440", "#4a3018", edge=4)
    ic.overlay(lambda d: [d.line([(x, 652), (x, BASE)], fill=(40, 24, 12, 150), width=3) for x in range(dx0 + 18, dx1, 18)])
    ic.fill(ic.poly_mask([(dx0 - 30, 646), (dx1 + 30, 646), (dx1 + 16, 618), (dx0 - 16, 618)]), SNOW[0], SNOW[1],
            noise=0.06)
    ic.outline([(dx0 - 30, 646), (dx1 + 30, 646), (dx1 + 16, 618), (dx0 - 16, 618)], 4)
    roof(ic)


# ---------------------------------------------------------------- yard, sledge, road
def fence(ic: Icon) -> None:
    """Plank yard fence with pointed boards and a roofed double gate; snow on every top."""
    x0, x1, top = 470, 1000, 660
    rnd = ic.random.uniform
    x = x0
    while x < x1:
        w = rnd(24, 32)
        t = top + rnd(-8, 8)
        pts = [(x, BASE), (x, t), (x + w / 2, t - 18), (x + w, t), (x + w, BASE)]
        ic.poly(pts, "#8a6844", "#4a3420", edge=4)
        ic.fill(ic.poly_mask([(x + 2, t + 2), (x + w / 2, t - 14), (x + w - 2, t + 2), (x + w / 2, t + 8)]), SNOW[0],
                SNOW[1], noise=0.05)
        x += w
    ic.rect((x0, 720, x1, 740), "#6e5034", "#3e2c1a", edge=4)
    ic.rect((x0, 830, x1, 850), "#6e5034", "#3e2c1a", edge=4)
    tint(ic, ic.mask("rectangle", (x0, top - 30, x1, BASE)), None, (40, 50, 80), 0.18)
    # the gate: two heavy posts and a little gable roof with snow
    for px in (716, 900):
        ic.rect((px - 18, 560, px + 18, BASE), "#7a5836", "#3e2a18", edge=4)
    ic.rect((704, 594, 912, 616), "#7a5836", "#3e2a18", edge=4)
    gr = [(686, 594), (808, 520), (930, 594), (930, 604), (808, 534), (686, 604)]
    ic.poly(gr, "#6e4a2c", "#3a2414", edge=4)
    sn = [(680, 590), (808, 506), (936, 590), (920, 598), (808, 530), (696, 598)]
    ic.fill(ic.poly_mask(sn), SNOW[0], SNOW[1], noise=0.06)
    ic.outline(sn, 4)


def sledge(ic: Icon) -> tuple[float, float]:
    """Post sledge: curled runners, a boarded box, mail bags under roped bast matting. Returns the
    shaft socket at its front."""
    rope_c = (150, 120, 80)
    load = [(836, 822), (846, 752), (884, 716), (950, 708), (996, 730), (1004, 822)]
    lm = ic.poly_mask(load)
    ic.fill(lm, "#b09a6a", "#5a4a2e", radial=(850, 700, 220), noise=0.2)
    ic.overlay(lambda d: [d.line([(x, 710), (x + 4, 822)], fill=(90, 70, 40, 120), width=3) for x in range(850, 1000, 14)], lm)
    for x in (880, 950):
        rope(ic, [(x - 6, 716), (x, 770), (x + 2, 822)], 5, rope_c)
    rope(ic, [(842, 780), (920, 770), (1002, 780)], 5, rope_c)
    ic.fill(ic.poly_mask([(862, 736), (884, 712), (950, 704), (990, 724), (950, 722), (890, 730)]), SNOW[0], SNOW[1],
            noise=0.05)
    ic.outline(load, 4)
    box = [(826, 812), (1006, 812), (1000, 900), (840, 900)]
    hboards(ic, box, "#94704a", "#4e3620", board=22)
    ic.outline(box, 5)
    for x in (860, 930, 986):
        ic.line([(x, 900), (x + 2, 928)], 12, (60, 40, 22))
    run = [(1006, 928), (860, 928), (820, 920), (800, 896), (806, 866), (826, 856), (836, 870), (824, 890), (846, 910),
           (1006, 912)]
    ic.poly(run, "#8a6440", "#4a3018", edge=4)
    ic.line([(1004, 930), (860, 930), (818, 922)], 6, (70, 70, 72))
    return (832, 870)


def hboards(ic: Icon, pts, c1="#8a6442", c2="#4e3522", board: float = 24) -> Image.Image:
    """Horizontal boards: per-board tone, lit top edge, dark joint below."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    rnd = ic.random.uniform
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = min(ys)
    while y < max(ys):
        h = board * rnd(0.85, 1.15)
        t = rnd(-1, 1)
        d.rectangle((min(xs), y, max(xs), y + h), fill=(255, 225, 180, int(26 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        d.line([(min(xs), y + 2), (max(xs), y + 2)], fill=(255, 230, 190, 50), width=3)
        d.line([(min(xs), y + h), (max(xs), y + h)], fill=(30, 18, 10, 150), width=4)
        y += h
    paste_clipped(ic, lay, m)
    return m


def verst(ic: Icon, x, top, bot) -> None:
    """Striped verst post of the post road."""
    w = 30
    m = ic.mask("rectangle", (x - w / 2, top, x + w / 2, bot))
    ic.fill(m, "#f0ece4", "#a8a49c", (x - w / 2, x + w / 2), vertical=False, noise=0.08)
    for i, y in enumerate(np.arange(top, bot, 40)):
        if i % 2:
            ic.fill(ic.intersect(m, ic.poly_mask([(x - w, y), (x + w, y - 14), (x + w, y + 26), (x - w, y + 40)])),
                    "#3a3634", "#141212", noise=0.08)
    tint(ic, ic.mask("rectangle", (x + 2, top, x + w, bot)), m, (20, 30, 50), 0.35, 4)
    ic.outline([(x - w / 2, top), (x + w / 2, top), (x + w / 2, bot), (x - w / 2, bot)], 4)
    ic.poly([(x - w / 2 - 8, top), (x + w / 2 + 8, top), (x + w / 2, top - 16), (x - w / 2, top - 16)], "#e8e4dc",
            "#9a968e", edge=4)


def snowfield(ic: Icon) -> Image.Image:
    top, bot, x0, x1 = BASE - 8, 978, 16, 1008
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#eef2f6", "#a2aec0", (top, bot), noise=0.08, chroma=0.03)
    rnd = ic.random.uniform

    def tracks(d):
        for y in (920, 956):  # runner tracks
            x = x0 + 20
            while x < x1 - 20:
                ln = rnd(80, 200)
                d.line([(x, y + rnd(-2, 2)), (x + ln, y + rnd(-2, 2))], fill=(110, 126, 160, 130), width=6)
                d.line([(x, y + 6), (x + ln, y + 6)], fill=(255, 255, 255, 120), width=3)
                x += ln + rnd(10, 40)
        for _ in range(30):  # hoof prints
            x, y = rnd(x0 + 30, x1 - 30), rnd(top + 20, bot - 12)
            d.ellipse((x - 8, y - 4, x + 8, y + 4), fill=(100, 116, 150, 110))

    ic.overlay(tracks, m)
    tint(ic, ic.mask("rectangle", (0, top, SIZE, top + 26)), m, (60, 80, 120), 0.3, 10)
    ic.outline(pts, 5)
    return m


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    ic.grade["gamma"] = 0.8
    fence(ic)
    house(ic)
    snowfield(ic)
    verst(ic, 34, 640, 930)
    tint(ic, ic.mask("ellipse", (430, GROUND - 22, 1010, GROUND + 22)), None, (40, 50, 80), 0.4, 14)
    sock = sledge(ic)
    hook = horse(ic, 486, GROUND, 0.92)
    for dy in (0, -14):
        ic.line([(hook[0], hook[1] + dy), (sock[0], sock[1] + dy)], 14 if dy == 0 else 10,
                (70, 46, 26) if dy == 0 else (150, 110, 70))
