"""Clove Grove: tall evergreen clove trees tipped with crimson bud clusters, buds drying on mats.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/clove_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/clove_grove

Identity: a tall clove tree whose crown is built of five or six overlapping leaf masses (lit from
the upper left, dark undersides and shadowed gaps, a jagged leafy outline), patches of pinkish-red
new flush on the top and the tips, and dark-red clumps of cone-shaped clove buds at the twig ends;
a smaller one behind it, a picker's ladder against the big tree; on the ground two woven palm
mats, the back one covered with raked dark red-brown dried cloves, the front one with bright red
buds just picked, a few loose buds on their edges; a basket of cloves.

Local helpers: ``gleaf`` (glossy leaf, from coffee_grove), ``buds`` (clump of cone-shaped clove
buds), ``flush`` (patch of pinkish-red new leaves), ``mass`` (one jagged leaf mass of the crown),
``clove_tree`` (crown of overlapping masses over a dark core), ``mat`` (woven palm mat lying flat
in perspective), ``paint_cloves``/``cloves`` (nail-shaped cloves, strewn over a surface in
perspective or placed one by one).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 57
REFS = ("fruit_orchard", "sugar_plantation", "perfumery", "tobacco_plantation")

LEAF = ("#3e6a32", "#0a1808")
FLUSH = ("#e0705c", "#782018")

FRESH = [((192, 42, 28), (100, 16, 10)), ((208, 60, 38), (110, 22, 12)), ((172, 34, 24), (88, 12, 8)),
         ((200, 72, 40), (104, 26, 12))]
DRIED = [((98, 42, 24), (40, 14, 8)), ((82, 34, 20), (34, 12, 6)), ((112, 54, 30), (48, 20, 10)),
         ((70, 30, 18), (28, 10, 6))]
BUDS = [((122, 24, 20), (178, 62, 48), (50, 8, 6)), ((106, 20, 18), (160, 50, 40), (44, 6, 4)),
        ((140, 34, 24), (192, 78, 56), (58, 12, 8))]


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def darker(cols, f):
    return tuple(tuple(int(min(255, v * f)) for v in rgb(c)) for c in cols)


def gleaf(ic: Icon, base, deg: float, length: float, width: float, colors=LEAF, droop: float = 0.15) -> None:
    """Glossy pointed leaf: lit/shadow halves by tone, a pale gloss sliver, faint midrib."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 16)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * math.sin(math.pi * t ** 0.8) for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), length * 1.15), noise=0.18, chroma=0.12)
    lower, nu = (s1, -n) if n[1] > 0 else (s2, n)
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (6, 14, 4), 0.30)
    gloss = [tuple(spine[k] + nu * hw[k] * 0.2) for k in range(3, 10)]
    gloss += [tuple(spine[k] + nu * hw[k] * 0.7) for k in range(9, 2, -1)]
    ic.shade(ic.poly_mask(gloss), (230, 244, 210), 0.3, blur=2)
    ic.outline(pts, 3, (14, 24, 8, 120))


def buds(ic: Icon, x: float, y: float, r: float, n: int) -> None:
    """Clump of clove buds fanning up from a twig end: each a dark-red cone (the long receptacle)
    widening to a small round head, lit side left, over a dark shadowed core; one blended layer."""
    rnd = ic.random
    items = []
    for _ in range(n):
        a = math.radians(rnd.uniform(-140, -40))
        L = r * rnd.uniform(0.7, 1.0)
        items.append((a, L, rnd.choice(BUDS)))
    items.sort(key=lambda it: -abs(math.cos(it[0])))  # outer ones first, upright ones in front

    def paint(dr):
        dr.ellipse((x - r * 0.55, y - r * 0.45, x + r * 0.55, y + r * 0.2), fill=(46, 12, 8, 230))
        for a, L, (mid, lit, dk) in items:
            ca, sa = math.cos(a), math.sin(a)
            nx, ny = -sa, ca
            tip = (x + ca * L, y + sa * L)
            w0, w1 = 2.5, r * 0.2
            cone = [(x + nx * w0, y + ny * w0), (tip[0] + nx * w1, tip[1] + ny * w1),
                    (tip[0] - nx * w1, tip[1] - ny * w1), (x - nx * w0, y - ny * w0)]
            dr.polygon([(px + 2, py + 2) for px, py in cone], fill=dk + (255,))
            dr.polygon(cone, fill=mid + (255,))
            side = 1 if nx < 0 else -1  # the edge facing left catches the light
            dr.line([(x + nx * w0 * side * 0.5, y + ny * w0 * side * 0.5),
                     (tip[0] + nx * w1 * side * 0.6, tip[1] + ny * w1 * side * 0.6)], fill=lit + (200,), width=3)
            hr = r * 0.2
            hx, hy = tip[0] + ca * hr * 0.6, tip[1] + sa * hr * 0.6
            dr.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=dk + (255,))
            dr.ellipse((hx - hr + 1.5, hy - hr + 1, hx + hr - 2, hy + hr - 2.5), fill=mid + (255,))
            dr.ellipse((hx - hr * 0.7, hy - hr * 0.8, hx, hy - hr * 0.1), fill=lit + (220,))

    ic.overlay(paint)


def flush(ic: Icon, x: float, y: float, r: float, up: float = -90) -> None:
    """Patch of pinkish-red new leaves (the clove's flush) sprouting from a crown tip."""
    rnd = ic.random
    for _ in range(rnd.randint(8, 10)):
        gleaf(ic, (x + rnd.uniform(-r, r) * 0.6, y + rnd.uniform(-r, r) * 0.25), up + rnd.uniform(-75, 75),
              rnd.uniform(0.9, 1.25) * r, r * 0.42, darker(FLUSH, rnd.uniform(0.85, 1.12)), 0.35)


def mass(ic: Icon, cx: float, cy: float, rx: float, ry: float, light: float, leaves: int) -> Image.Image:
    """One leaf mass of the crown: a jagged, leafy outline, lit from the upper left with a dark
    underside, the darkness of a gap cast onto what lies behind its lower right, leaves along the
    rim pointing outwards. Returns its mask."""
    rnd = ic.random
    pts = []
    for k in range(40):
        a = 2 * math.pi * k / 40
        f = (1.0 if k % 2 else 0.84) * rnd.uniform(0.9, 1.08)
        pts.append((cx + math.cos(a) * rx * f, cy + math.sin(a) * ry * f))
    m = ic.poly_mask(pts)
    ic.shade(ic.poly_mask([(px + rx * 0.12, py + ry * 0.16) for px, py in pts]), (4, 8, 2), 0.6, blur=10)
    lit = tuple(int(min(255, v * light)) for v in rgb("#4a7a36"))
    ic.fill(m, lit, "#081404", radial=(cx - rx * 0.7, cy - ry * 0.8, max(rx, ry) * 2.3), noise=0.3, chroma=0.12)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 1.3, cy + ry * 0.1, cx + rx * 1.4, cy + ry * 1.8))),
             (4, 10, 2), 0.5, blur=14)
    items = []
    for _ in range(leaves):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.35, 0.95) ** 0.7
        px, py = cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr
        items.append((py, px, a))
    items.sort()
    for py, px, a in items:
        f = light * (1.02 - 0.45 * (math.cos(a) * 0.5 + math.sin(a) * 0.7))
        gleaf(ic, (px, py), math.degrees(a) + rnd.uniform(-30, 30), rnd.uniform(36, 56), rnd.uniform(14, 19),
              darker(LEAF, f), 0.3)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 1.2, cy - ry * 1.2, cx + rx * 0.2, cy - ry * 0.05))),
             (236, 242, 196), 0.14, blur=16)
    return m


def clove_tree(ic: Icon, x: float, top: float, bot: float, hw: float, light: float = 1.0,
               bud_spots=(), flush_spots=(), stems: bool = True) -> Image.Image:
    """Clove tree: short grey stems, a dark core, then five or six overlapping leaf masses laid top
    to bottom (each lower one in front); the flush patches and bud clumps go on the tips and top
    (``*_spots`` are (u, t) in crown units: u = -1..1 across, t = 0..1 down). Returns the crown mask."""
    H = bot - top
    if stems:
        for dx, lean in ((-18, -30), (14, 26)):
            ic.line([(x + dx, bot + 140), (x + dx * 0.3 + lean, bot - 40)], 30, (60, 52, 44))
            ic.line([(x + dx - 4, bot + 140), (x + dx * 0.3 + lean - 4, bot - 40)], 10, (170, 160, 140, 140))
    core = ic.poly_mask(ic.jitter(x, top + H * 0.52, hw * 0.8, H * 0.42, 18, 0.08))
    ic.fill(core, "#16280e", "#040a02", (top, bot), noise=0.3)
    acc = core
    masses = ((0.0, 0.15, 0.52, 0.17, 1.15, 30), (-0.44, 0.35, 0.58, 0.19, 1.1, 34),
              (0.46, 0.4, 0.55, 0.19, 0.85, 30), (-0.46, 0.63, 0.6, 0.19, 1.0, 34),
              (0.42, 0.67, 0.6, 0.19, 0.78, 34), (-0.04, 0.85, 0.72, 0.15, 0.82, 36))
    for u, t, fx, fy, lt, n in masses:
        acc = union(acc, mass(ic, x + u * hw, top + t * H, fx * hw, fy * H, lt * light, n))
    ic.shade(ic.intersect(acc, ic.mask("ellipse", (x - hw * 0.1, top + H * 0.3, x + hw * 1.6, bot + H * 0.4))),
             (6, 12, 4), 0.35, blur=40)
    for u, t in flush_spots:
        flush(ic, x + u * hw, top + t * H, 54, -90 + 50 * u)
    for u, t in bud_spots:
        buds(ic, x + u * hw, top + t * H, 34, 12)
    return acc


def mat(ic: Icon, pts, base=("#c0a06a", "#8a6c42")) -> Image.Image:
    """Woven palm-leaf mat lying flat: pale plaited strips in two directions, a bound darker edge."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, base[0], base[1], (min(ys), max(ys)), noise=0.28, chroma=0.1)

    def weave(dr):
        for x in np.arange(-400, 1400, 22):
            dr.line([(x, min(ys)), (x + (max(ys) - min(ys)) * 0.9, max(ys))], fill=(70, 50, 24, 60), width=3)
            dr.line([(x, min(ys)), (x - (max(ys) - min(ys)) * 0.9, max(ys))], fill=(250, 232, 190, 45), width=3)
        for _ in range(30):
            x, y = rnd.uniform(0, SIZE), rnd.uniform(min(ys), max(ys))
            dr.ellipse((x - 30, y - 8, x + 30, y + 8), fill=(60, 40, 20, 30))

    ic.overlay(weave, m)
    ic.outline(list(pts), 9, (110, 82, 48, 220))
    ic.outline(list(pts), 3, (40, 28, 14, 160))
    return m


def paint_cloves(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Nail-shaped cloves (x, y, size, (mid, dark), angle): a short stem and a round head, each with a
    darker underside and a small highlight."""

    def paint(dr):
        for x, yy, size, (mid, dk), a in items:
            L = size * 1.6
            ex, ey = x + math.cos(a) * L, yy + math.sin(a) * L * 0.5
            dr.line([(x + 1, yy + 3), (ex + 1, ey + 3)], fill=dk + (160,), width=int(size * 0.9))
            dr.line([(x, yy), (ex, ey)], fill=mid + (255,), width=max(3, int(size * 0.7)))
            r = size * 0.62
            dr.ellipse((x - r, yy - r + 2, x + r, yy + r + 2), fill=dk + (255,))
            dr.ellipse((x - r, yy - r, x + r, yy + r - 1), fill=mid + (255,))
            dr.ellipse((x - r * 0.6, yy - r * 0.7, x, yy - r * 0.1), fill=tuple(min(255, int(v * 1.4)) for v in mid) + (200,))

    ic.overlay(paint, clip)


def cloves(ic: Icon, clip: Image.Image, y0: float, y1: float, x0: float, x1: float, step: float, size: float,
           palettes, density=None) -> None:
    """Cloves strewn over a surface in perspective; ``density(x, y)`` in 0..1 thins them out."""
    rnd = ic.random
    items = []
    y = y0 + 4
    while y < y1:
        s = 0.75 + 0.25 * (y - y0) / max(y1 - y0, 1)
        x = x0 + rnd.uniform(0, step)
        while x < x1:
            if density is None or rnd.random() < density(x, y):
                items.append((x + rnd.uniform(-4, 4), y + rnd.uniform(-3, 3), size * s, rnd.choice(palettes),
                              rnd.uniform(0, 2 * math.pi)))
            x += step * s * rnd.uniform(0.6, 1.0)
        y += step * 0.45 * s
    items.sort(key=lambda it: it[1])
    paint_cloves(ic, items, clip)


def loose(ic: Icon, edge, n: int, size: float, palettes) -> None:
    """A few bigger single buds dropped along a mat edge (``edge`` = two end points)."""
    rnd = ic.random
    (xa, ya), (xb, yb) = edge
    items = []
    for _ in range(n):
        t = rnd.random()
        items.append((xa + (xb - xa) * t, ya + (yb - ya) * t + rnd.uniform(-8, 8), size * rnd.uniform(0.85, 1.15),
                      rnd.choice(palettes), rnd.uniform(0, 2 * math.pi)))
    items.sort(key=lambda it: it[1])
    paint_cloves(ic, items)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.55
    ic.grade["mute"] = 0.9

    # ---- smaller clove tree behind on the right
    clove_tree(ic, 640, 190, 640, 128, 0.9,
               bud_spots=((-0.8, 0.3), (0.85, 0.42), (-0.9, 0.62), (0.3, 0.1), (0.8, 0.7)),
               flush_spots=((0.0, 0.02), (-0.7, 0.24)))

    # ---- ground strip
    top = [(64, 930)] + [(x, 900 + rnd.uniform(-12, 10)) for x in np.linspace(110, 960, 12)] + [(1010, 926)]
    ic.poly(top + [(1012, 996), (520, 1006), (60, 998)], "#735a3a", "#4a3a26", noise=0.32, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(80, 990), rnd.uniform(920, 994)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)

    # ---- back mat: dried dark red-brown cloves raked into ridges
    back = [(476, 756), (740, 748), (990, 752), (1014, 870), (730, 876), (440, 880)]
    B = mat(ic, back)

    def ridges(x, y):
        return 0.15 + 0.85 * max(0.0, math.sin((x - 0.3 * y) / 40)) ** 0.5

    inner = ic.poly_mask([(498, 770), (976, 766), (994, 858), (470, 864)])
    ic.fill(inner, "#522010", "#301008", (766, 864), noise=0.3)
    cloves(ic, inner, 766, 862, 470, 996, 12, 9, DRIED, ridges)
    ic.shade(ic.intersect(B, ic.mask("rectangle", (0, 744, SIZE, 768))), alpha=0.25, blur=6)
    loose(ic, ((600, 874), (900, 872)), 6, 15, DRIED)
    ic.line([(930, 856), (1000, 700)], 10, (40, 28, 16, 120))  # rake leaning on the mat
    ic.line([(926, 852), (996, 696)], 8, (168, 130, 84))
    ic.line([(880, 862), (970, 858)], 12, (124, 90, 56))

    # ---- the big clove tree with a picker's ladder
    clove_tree(ic, 250, 62, 716, 196, 1.0,
               bud_spots=((-0.85, 0.3), (0.62, 0.22), (-0.95, 0.56), (0.9, 0.5), (0.2, 0.04), (0.85, 0.74)),
               flush_spots=((-0.15, 0.04), (-0.75, 0.2), (0.55, 0.3)))
    ic.shade(ic.mask("ellipse", (120, 830, 400, 900)), alpha=0.4, blur=12)
    for x0, x1 in ((452, 392), (510, 444)):  # ladder rails leaning into the crown
        ic.line([(x0 + 4, 900), (x1 + 4, 420)], 16, (40, 28, 16, 150))
        ic.line([(x0, 896), (x1, 416)], 13, (164, 128, 84))
        ic.line([(x0 - 3, 896), (x1 - 3, 416)], 4, (220, 190, 140, 150))
    for k in range(9):
        t = (k + 0.6) / 9.6
        ya = 896 - 480 * t
        ic.line([(452 - 60 * t, ya), (510 - 66 * t, ya)], 9, (130, 98, 62))

    # ---- front mat: bright red buds just picked, spread in drifts, a few loose on the edge
    front = [(96, 878), (600, 872), (640, 990), (50, 996)]
    F = mat(ic, front, ("#c8aa74", "#94764a"))
    finner = ic.poly_mask([(120, 892), (578, 888), (608, 978), (82, 982)])
    ic.fill(finner, "#a02a16", "#6a1a0c", (888, 982), noise=0.3)
    cloves(ic, finner, 888, 980, 84, 610, 13, 10, FRESH)
    loose(ic, ((110, 884), (590, 880)), 7, 16, FRESH)
    loose(ic, ((70, 990), (630, 986)), 5, 17, FRESH)

    # ---- a filled sack of dried cloves between the mats and the basket
    ic.shade(ic.mask("ellipse", (660, 976, 830, 1004)), alpha=0.45, blur=8)
    ic.sack(742, 998, 132, 118, "#a07c4a")
    ic.shade(ic.mask("ellipse", (660, 870, 760, 1000)), (255, 240, 210), 0.1, blur=20)
    ic.fill(ic.mask("ellipse", (706, 876, 780, 898)), "#4a2414", "#2a120a")
    loose(ic, ((670, 996), (820, 994)), 6, 14, DRIED)

    # ---- basket of dried cloves, bottom right
    ic.shade(ic.mask("ellipse", (820, 966, 1016, 1002)), alpha=0.45, blur=8)
    ic.fill(ic.mask("ellipse", (842, 872, 1002, 918)), "#4a2414", "#2a120a")
    cloves(ic, ic.mask("ellipse", (842, 858, 1002, 918)), 858, 916, 842, 1002, 12, 6.5, DRIED)
    ic.basket(838, 894, 1006, 1000)

    # ---- dappled shade across the scene
    for _ in range(14):
        x, y = rnd.uniform(60, 1000), rnd.uniform(400, 900)
        r = rnd.uniform(30, 60)
        ic.shade(ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), (12, 16, 6), 0.12, blur=18)
