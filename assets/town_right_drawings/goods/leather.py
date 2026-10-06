"""Leather: a tanned ox hide stretched on a murrey field; crossed leatherworker's round knives behind the shield."""

import math

FIELD = "#6a2838"
SEED = 23


def _round_knife(icon, loc, mirror, k):
    L = k.CROSS_LEN
    # turned wooden handle with a ferrule
    k.rod(icon, *loc([(0, 640), (0, 880)]), 50, (96, 96, 96))
    k.rod(icon, *loc([(0, 880), (0, 930)]), 58, (190, 190, 190))
    # half-moon blade, edge towards the tip
    edge = [(150 * math.cos(t), 930 + 150 * math.sin(t)) for t in [i * math.pi / 30 for i in range(31)]]
    back = [(150 * math.cos(t), 930 + 44 * math.sin(t)) for t in [math.pi - i * math.pi / 30 for i in range(31)]]
    blade = loc(edge + back)
    m = icon.poly_mask(blade)
    c = loc([(0, 930)])[0]
    tip = loc([(0, L)])[0]
    k.dfill(icon, m, c, (tip[0] - c[0], tip[1] - c[1]), 160,
            ((0, (110, 110, 110)), (0.45, (170, 170, 170)), (0.7, (240, 240, 240)), (0.85, (150, 150, 150)),
             (1, (220, 220, 220))), noise=0.08)
    k.contour(icon, m)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _round_knife(ic, loc, mirror, k))


def charge(icon, k):
    cx, cy = 512, 470
    # stretched hide: body with four legs, neck and tail stubs; slightly irregular
    half = [(0, -246), (38, -236), (70, -258), (106, -282), (128, -250), (112, -200), (150, -150), (188, -150),
            (196, -112), (164, -60), (160, 40), (176, 110), (204, 150), (192, 196), (140, 198), (110, 240),
            (60, 250), (24, 280), (0, 300)]
    rnd = icon.random
    right = [(cx + x + rnd.uniform(-5, 5), cy + y + rnd.uniform(-5, 5)) for x, y in half]
    left = [(cx - x + rnd.uniform(-5, 5), cy + y + rnd.uniform(-5, 5)) for x, y in half[::-1]]
    pts = right + left[1:-1]
    m = icon.poly_mask(pts)
    k.rfill(icon, m, (cx - 40, cy - 80), 330,
            ((0, (226, 178, 118)), (0.45, (190, 132, 74)), (0.8, (140, 88, 44)), (1, (96, 56, 26))), noise=0.22)
    # spine shading and mottling of the grain
    k.tint(icon, icon.mask("rectangle", (cx - 18, cy - 250, cx + 18, cy + 290)), m, (90, 50, 20), 0.35, blur=14)
    for _ in range(22):
        x, y = cx + rnd.uniform(-150, 150), cy + rnd.uniform(-200, 220)
        r = rnd.uniform(12, 34)
        k.tint(icon, k.ell(icon, x, y, r, r * 0.7), m, (70, 40, 16) if rnd.random() < 0.6 else (250, 210, 160),
               rnd.uniform(0.08, 0.18), blur=8)
    # darker, thinner edge where the hide was trimmed, and the stretching holes
    ring = k.subtract(m, m.filter(k.ImageFilter.MinFilter(25)))
    k.tint(icon, ring, m, (60, 30, 12), 0.45, blur=6)
    for (x, y), _ in k.path_points(pts + [pts[0]], 46):
        dx, dy = cx - x, cy - y
        n = math.hypot(dx, dy) or 1
        hx, hy = x + dx / n * 22, y + dy / n * 22
        icon.draw.ellipse((hx - 6, hy - 6, hx + 6, hy + 6), fill=(40, 20, 10, 255))
    k.contour(icon, m)
