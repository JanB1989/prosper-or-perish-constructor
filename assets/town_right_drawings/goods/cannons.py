"""Cannons: a bronze cannon on a wheeled field carriage on a gules field; crossed rammer and sponge staves
behind the shield and a pile of shot at each lower side."""

import math

FIELD = "#8e3328"
SEED = 35


def _rammer(icon, loc, mirror, k):
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 0), (0, L - 140)]), 30, (120, 120, 120))
    head = loc([(-48, L - 150), (48, L - 150), (48, L - 10), (-48, L - 10)])
    m = icon.poly_mask(head)
    a, b = loc([(-48, L - 80), (48, L - 80)])
    k.cyl(icon, m, a, b, 96, (190, 190, 190) if not mirror else (150, 150, 150))
    if mirror:  # sponge: fleecy texture
        k.strokes(icon, m, (40, 40, 40), 140, 60, 12, 4, 0.3, (10, 26))
    else:
        for v in (L - 120, L - 40):
            k.rod(icon, *loc([(-50, v), (50, v)]), 12, (120, 120, 120))
    k.contour(icon, m)


def _shot(icon, sx, mirror, k):
    for x, y in ((90, 940), (180, 940), (270, 944), (136, 870), (226, 872), (182, 802)):
        k.ball(icon, sx(x), y, 46, (170, 170, 170))


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _rammer(ic, loc, mirror, k))
    k.flank(icon, lambda ic, sx, mirror: _shot(ic, sx, mirror, k))


def charge(icon, k):
    bronze = (184, 138, 62)
    # carriage cheek and trail (behind the wheel)
    cheek = [(330, 640), (420, 560), (590, 520), (620, 560), (600, 640), (430, 690), (340, 730), (318, 712)]
    k.block(icon, cheek, (124, 80, 44))
    # barrel, elevated towards the upper right
    org, ang = (370, 560), -24

    def P(pts):
        return k.rotated(pts, org, ang)

    barrel = P([(0, -50), (60, -56), (330, -38), (350, -46), (360, -46), (360, 46), (350, 46), (330, 38), (60, 56),
                (0, 50)])
    m = icon.poly_mask(barrel)
    a, b = P([(150, -56), (150, 56)])
    k.dfill(icon, m, a, (b[0] - a[0], b[1] - a[1]), 112,
            ((0, (150, 106, 40)), (0.25, (250, 214, 130)), (0.5, bronze), (1, (80, 52, 18))), noise=0.1)
    for x, w in ((60, 120), (150, 104), (250, 90)):
        k.rod(icon, *P([(x, -w / 2), (x, w / 2)]), 16, (200, 156, 72))
    k.contour(icon, m)
    k.ball(icon, *P([(-24, 0)])[0], 26, bronze)  # cascabel
    muzzle = P([(360, 0)])[0]
    icon.draw.ellipse((muzzle[0] - 16, muzzle[1] - 24, muzzle[0] + 12, muzzle[1] + 24), fill=(30, 20, 12, 255))
    # spoked wheel in front
    wx, wy, r = 520, 640, 106
    rim_m = k.subtract(k.ell(icon, wx, wy, r), k.ell(icon, wx, wy, r - 26))
    for i in range(8):
        t = math.radians(i * 45 + 10)
        k.rod(icon, (wx, wy), (wx + math.cos(t) * (r - 20), wy + math.sin(t) * (r - 20)), 16, (140, 96, 54))
    icon.fill(rim_m, (150, 104, 60), (80, 50, 26), (wy - r, wy + r))
    iron = k.subtract(k.ell(icon, wx, wy, r), k.ell(icon, wx, wy, r - 9))
    icon.fill(iron, (90, 90, 96), (40, 40, 44), (wy - r, wy + r))
    k.contour(icon, k.ell(icon, wx, wy, r))
    k.contour(icon, k.ell(icon, wx, wy, r - 26), 5)
    k.ball(icon, wx, wy, 24, (110, 110, 116))
