"""Ivory Hunting Camp (ivory_hunting_camp): a canvas ridge tent under a flat-topped acacia, a drying
rack hung with meat strips, and a big pile of curved elephant tusks.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/ivory_hunting_camp/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/ivory_hunting_camp

Identity: two big cream tusks stood on their roots under the rack, curving in until their tips cross (one lying in
front, its crescent turned up), against
a patched tan tent with an open dark entrance; the umbrella crown of an acacia over the camp says
savanna, the forked-post rack with a few wide reddish meat strips and two leaning spears say hunting camp.

Local helpers: ``tusk`` (curved tapering ivory with a lit upper side, root cavity and growth rings),
``acacia`` (flat layered umbrella crown), ``tuft`` (dry grass), ``rim_darken`` (from ocean_fishery).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("peasants_hunting_grounds", "elephant_hunting_grounds", "tambo", "caravan_stop")

TIMBER = (120, 88, 58)
CANVAS = ("#e6c68c", "#a07a44")
EARTH = ("#a4683e", "#5a3219")


# ---------------------------------------------------------------- helpers
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


def tusk(ic: Icon, base, deg: float, length: float, width: float, bend: float = 0.22, root: bool = True) -> Image.Image:
    """Elephant tusk from its root at ``base`` towards ``deg`` (0 = right, 180 = left), curving towards
    the upper side by ``bend``. Cream ivory lit on the upper side, darker yellowed root, growth rings,
    the hollow root seen as a dark ellipse. Returns the tusk mask."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    if n[1] > 0:
        n = -n  # n points up
    b = np.array(base, float)
    ts = np.linspace(0, 1, 30)
    spine = [b + d * length * t + n * bend * length * t * t for t in ts]
    hw = [width / 2 * (1 - t ** 1.6) ** 0.55 * (1 - 0.18 * t) * (1 + 0.04 * math.sin(7 * t)) + 2 for t in ts]
    up = [p + n * w for p, w in zip(spine, hw)]
    lo = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in up + lo[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#f8eed2", "#b8986a", radial=(min(xs) + (max(xs) - min(xs)) * 0.35, min(ys) - width * 0.4,
                                             max(length * 0.9, 1)), noise=0.12, chroma=0.08)
    # shadow on the lower side, a highlight streak along the upper side
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lo[::-1]]), (104, 66, 30), 0.45, blur=4)
    hi = [tuple(spine[k] + n * hw[k] * 0.35) for k in range(2, 24)] + \
         [tuple(spine[k] + n * hw[k] * 0.8) for k in range(23, 1, -1)]
    ic.shade(ic.poly_mask(hi), (255, 252, 236), 0.45, blur=3)
    # yellowed, stained root third
    stain = [tuple(p) for p in up[:9]] + [tuple(p) for p in lo[:9][::-1]]
    ic.shade(ic.intersect(ic.poly_mask(stain), m), (120, 72, 28), 0.55, blur=12)
    base_band = [tuple(p) for p in up[:3]] + [tuple(p) for p in lo[:3][::-1]]
    ic.shade(ic.intersect(ic.poly_mask(base_band), m), (70, 40, 16), 0.5, blur=4)
    for k in (4, 10):  # growth rings
        ic.line([tuple(up[k]), tuple(spine[k] + d * 3), tuple(lo[k])], 2, (110, 80, 40, 55))
    # hollow root end: slanted ellipse, yellow rim, dark cavity
    r = hw[0]
    cx, cy = b
    if not root:
        ic.outline(pts, 6, (46, 30, 14, 235))
        return m
    ic.fill(ic.mask("ellipse", (cx - r * 0.45, cy - r, cx + r * 0.45, cy + r)), "#a87a44", "#6a4420", noise=0.1)
    ic.fill(ic.mask("ellipse", (cx - r * 0.28, cy - r * 0.68, cx + r * 0.28, cy + r * 0.68)), "#3a2412", "#1a0e06",
            noise=0.1)
    ic.outline(pts, 6, (46, 30, 14, 235))
    return m


def acacia(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> Image.Image:
    """Flat-topped umbrella crown in two thin layers: olive blobs, leaf dabs, dark underside."""
    rnd = ic.random
    m = blank()
    blobs = []
    for layer, (dy, sx, k) in enumerate(((-ry * 0.35, 0.7, 12), (ry * 0.2, 1.0, 18))):
        for _ in range(k):
            u = rnd.uniform(-1, 1) * sx
            blobs.append((cx + u * rx, cy + dy + rnd.uniform(-ry * 0.2, ry * 0.2), rx * rnd.uniform(0.14, 0.22),
                          ry * rnd.uniform(0.3, 0.45)))
    blobs.sort(key=lambda b: b[1])
    for bx, by, brx, bry in blobs:
        bm = ic.poly_mask(ic.jitter(bx, by, brx, bry, 24, 0.1))
        ic.fill(bm, "#8a9448", "#2c3416", radial=(bx - brx * 0.6, by - bry * 1.2, brx * 2.2), noise=0.3, chroma=0.14)
        m = union(m, bm)
    x0, x1, y0, y1 = cx - rx * 1.2, cx + rx * 1.2, cy - ry * 1.2, cy + ry * 1.2

    def dabs(dr):
        for _ in range(1400):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            v = (y - cy) / ry
            r = rnd.uniform(3, 7)
            col = (176, 180, 110, 75) if rnd.random() < 0.45 - 0.45 * v else (26, 32, 12, 75)
            dr.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.5), fill=col)

    ic.overlay(dabs, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, cy + ry * 0.1, SIZE, SIZE))), (16, 20, 6), 0.45, blur=16)
    return m


def tuft(ic: Icon, x: float, base: float, h: float) -> None:
    rnd = ic.random

    def paint(d):
        for _ in range(12):
            a = math.radians(rnd.uniform(-150, -30))
            L = h * rnd.uniform(0.5, 1.0)
            col = (206, 176, 104, 230) if rnd.random() < 0.6 else (122, 96, 50, 230)
            d.line([(x + rnd.uniform(-8, 8), base), (x + math.cos(a) * L, base + math.sin(a) * L)], fill=col, width=4)

    ic.overlay(paint)


# ---------------------------------------------------------------- scene
def tree(ic: Icon) -> None:
    rnd = ic.random
    trunk = [(196, 790), (214, 700), (226, 560), (236, 420), (262, 420), (262, 560), (266, 700), (290, 790)]
    ic.poly(trunk, "#7a6450", "#3a2c20", span=(210, 270), vertical=False, noise=0.3, edge=3)
    for p0, p1, w in (((244, 440), (120, 250), 20), ((250, 430), (400, 230), 20), ((236, 330), (270, 200), 14),
                      ((150, 290), (60, 220), 10), ((370, 260), (470, 214), 10)):
        ic.line([p0, p1], w, (84, 66, 50))
        ic.line([(p0[0] - 3, p0[1] - 2), (p1[0] - 3, p1[1] - 2)], max(w // 3, 3), (150, 128, 104, 140))
    acacia(ic, 262, 196, 250, 64)
    for _ in range(8):
        x, y = rnd.uniform(214, 262), rnd.uniform(440, 760)
        ic.shade(ic.mask("ellipse", (x - 6, y - 14, x + 6, y + 14)), (220, 210, 180), 0.15, blur=3)


def ground(ic: Icon) -> None:
    rnd = ic.random
    top = [(16, 790)] + [(x, 766 + rnd.uniform(-12, 10)) for x in np.linspace(70, 960, 12)] + [(1008, 786)]
    bottom = [(1010, 930)]
    for x in np.linspace(960, 60, 16):
        bottom.append((x + rnd.uniform(-14, 14), 944 + 10 * math.sin(x / 90) + rnd.uniform(-14, 12)))
    bottom.append((14, 928))
    pts = top + bottom
    ic.poly(pts, EARTH[0], EARTH[1], noise=0.32, edge=3)
    ic.shade(ic.intersect(ic.poly_mask(pts), ic.mask("rectangle", (0, 900, SIZE, SIZE))), (50, 24, 8), 0.3, blur=14)
    for _ in range(50):
        x, y = rnd.uniform(40, 990), rnd.uniform(790, 950)
        ic.shade(ic.mask("ellipse", (x - 14, y - 5, x + 14, y + 5)), (255, 230, 190) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)


def rack(ic: Icon) -> None:
    """Two forked posts, one cross pole, a few wide strips of drying meat with gaps between them."""
    rnd = ic.random
    L, R, Y = 624, 968, 318
    for x in (L, R):
        ic.beam((x, 830), (x + rnd.uniform(-6, 6), Y - 10), 22, TIMBER)
        ic.line([(x - 4, 820), (x - 4, Y)], 5, (170, 132, 92, 150))
        ic.line([(x, Y + 4), (x - 30, Y - 46)], 13, (100, 74, 48))
        ic.line([(x, Y + 4), (x + 28, Y - 42)], 13, (100, 74, 48))
    ic.beam((L - 40, Y + 6), (R + 36, Y - 4), 18, (130, 96, 62))
    ic.line([(L - 40, Y), (R + 36, Y - 10)], 5, (180, 144, 100, 170))
    for x, h, w in ((690, 150, 52), (776, 120, 46), (858, 160, 56), (930, 116, 40)):
        y0 = Y + 10 - (x - L) / (R - L) * 10
        cx = x + rnd.uniform(-4, 4)
        strip = [(cx - w / 2, y0), (cx + w / 2, y0), (cx + w * 0.42, y0 + h * 0.6), (cx + w * 0.3, y0 + h),
                 (cx - w * 0.1, y0 + h + 12), (cx - w * 0.44, y0 + h * 0.7)]
        m = ic.poly_mask(strip)
        ic.fill(m, "#b85a3c", "#5a2214", (cx - w / 2, cx + w / 2), vertical=False, noise=0.3, chroma=0.14)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (cx - w / 2, y0, cx - w * 0.2, y0 + h + 20))), (250, 200, 170),
                 0.25, blur=4)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (0, y0 + h * 0.65, SIZE, SIZE))), (30, 8, 2), 0.35, blur=10)
        ic.outline(strip, 4, (48, 18, 8, 220))
        ic.line([(cx - 10, y0 - 8), (cx + 8, y0 + 10)], 6, (200, 180, 140))
    # shade under the pole
    ic.shade(ic.mask("rectangle", (L, Y, R, Y + 34)), alpha=0.25, blur=10)


def tent(ic: Icon) -> None:
    rnd = ic.random
    apex, back_apex = (322, 380), (560, 364)
    fl, fr, br = (128, 812), (516, 812), (700, 790)
    # side roof plane going back to the right
    side = [apex, back_apex, br, fr]
    ic.fill(ic.poly_mask(side), "#c8a066", "#7e5a30", (360, 812), noise=0.22)
    for f in (0.3, 0.55, 0.8):  # sagging canvas between the ridge supports
        a = (apex[0] + (back_apex[0] - apex[0]) * f, apex[1] + (back_apex[1] - apex[1]) * f)
        b = (fr[0] + (br[0] - fr[0]) * f, fr[1] + (br[1] - fr[1]) * f)
        ic.shade(ic.poly_mask([(a[0] - 4, a[1]), (a[0] + 10, a[1]), (b[0] + 16, b[1]), (b[0] - 4, b[1])]), alpha=0.18,
                 blur=10)
    ic.shade(ic.poly_mask(side), (30, 18, 8), 0.48)
    ic.shade(ic.poly_mask([apex, back_apex, (back_apex[0] + 20, back_apex[1] + 60), (apex[0] + 30, apex[1] + 70)]),
             (255, 240, 200), 0.18, blur=8)
    ic.outline(side, 4)
    # front triangle with an open entrance and tied-back flaps
    front = [apex, fr, fl]
    ic.fill(ic.poly_mask(front), CANVAS[0], CANVAS[1], radial=(200, 420, 520), noise=0.22)
    door = [(322, 470), (392, 812), (252, 812)]
    ic.poly(door, "#2c2016", "#120c06", edge=0)
    ic.poly([(322, 470), (252, 812), (206, 812), (296, 520)], "#c4aa78", "#7a6040", edge=3)
    ic.poly([(322, 470), (392, 812), (430, 812), (346, 520)], "#a88e5e", "#62492c", edge=3)
    # patches and seams
    ic.poly([(186, 640), (236, 632), (240, 690), (180, 700)], "#b8a070", "#8a7048", edge=3)
    ic.poly([(430, 600), (470, 596), (478, 648), (436, 652)], "#c6ae80", "#8e7450", edge=3)
    ic.shade(ic.poly_mask([apex, (fr[0], fr[1]), (fr[0] - 120, fr[1])]), (40, 24, 10), 0.3, blur=16)
    ic.shade(ic.poly_mask([apex, (fl[0], fl[1]), (fl[0] + 80, fl[1])]), (255, 240, 200), 0.2, blur=10)
    ic.outline(front, 4)
    # lit ridge
    ic.line([(apex[0] + 6, apex[1] + 4), (back_apex[0] - 4, back_apex[1] + 4)], 7, (250, 232, 190, 200))
    ic.beam((apex[0], apex[1] + 6), (apex[0] - 4, apex[1] - 60), 14, TIMBER)
    ic.beam((back_apex[0], back_apex[1] + 6), (back_apex[0] + 2, back_apex[1] - 44), 12, TIMBER)
    # guy rope and peg on the left
    for (x0, y0), (px, py) in ((((apex[0] - 10, apex[1] + 20)), (60, 830)), ((back_apex[0] + 6, back_apex[1] + 16), (770, 840)),
                               ((200, 640), (96, 852))):
        ic.line([(x0, y0), (px, py - 10)], 7, (40, 28, 16, 200))
        ic.line([(x0, y0), (px, py - 10)], 3, (200, 170, 120, 220))
        ic.rect((px - 8, py - 22, px + 8, py + 14), "#8a6442", "#4a3220", edge=3)
    ic.shade(ic.mask("ellipse", (100, 790, 740, 850)), alpha=0.35, blur=12)


def spears(ic: Icon) -> None:
    for (x0, y0), (x1, y1) in (((1004, 830), (930, 190)), ((990, 836), (1016, 214))):
        ic.line([(x0, y0), (x1, y1)], 12, (40, 28, 18, 220))
        ic.line([(x0, y0), (x1, y1)], 7, (150, 112, 74))
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        tip = (x1 + ux * 90, y1 + uy * 90)
        head = [(x1, y1), (x1 + ux * 30 + nx * 14, y1 + uy * 30 + ny * 14), tip,
                (x1 + ux * 30 - nx * 14, y1 + uy * 30 - ny * 14)]
        ic.poly(head, "#b4b4ae", "#5a5a58", edge=4)
        ic.line([(x1 - ux * 6, y1 - uy * 6), (x1 + ux * 6, y1 + uy * 6)], 14, (90, 60, 36))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.84
    ic.grade["gamma"] = 0.64
    tree(ic)
    ground(ic)
    rack(ic)
    tent(ic)
    spears(ic)
    ic.shade(ic.mask("ellipse", (480, 880, 1016, 950)), alpha=0.45, blur=14)
    # two big tusks stood on their roots under the rack, curving in until their tips cross: an ivory arch
    for x in (656, 944):
        ic.shade(ic.mask("ellipse", (x - 70, 878, x + 70, 918)), alpha=0.5, blur=8)
    tusk(ic, (656, 900), -96, 450, 104, 0.42, root=False)
    tusk(ic, (944, 900), -84, 450, 104, 0.42, root=False)
    # one lying in front, its crescent turned up
    ic.shade(ic.mask("ellipse", (520, 880, 960, 936)), alpha=0.45, blur=10)
    tusk(ic, (560, 912), -9, 380, 92, 0.36)
    for x in (80, 150, 470, 560, 380):
        tuft(ic, x + rnd.uniform(-10, 10), rnd.uniform(880, 940), rnd.uniform(40, 70))
    rim_darken(ic)
