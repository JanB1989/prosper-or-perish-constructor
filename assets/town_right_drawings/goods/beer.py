"""Beer: a hooped wooden tankard brimming with foam on an azure field; hop bines with leaves and cones climb
both sides of the shield."""

import math

FIELD = "#2f548a"
SEED = 30


def _hop_leaf(icon, k, base, ang, length):
    """Broad, serrated hop leaf on a short stalk."""
    greys = dict(colors=((214, 214, 214), (70, 70, 70)), rib=(150, 150, 150), vein=(80, 80, 80), edge=(40, 40, 40))
    icon.leaf(base, ang, length, length * 0.78, droop=0.18, **greys)


def _cone(icon, k, x, y, s):
    """Hop cone: an ovoid of overlapping bracts in staggered rows."""
    body = k.ell(icon, x, y, s * 0.62, s)
    icon.fill(body, (150, 150, 150), (70, 70, 70), (y - s, y + s))
    for row in range(5):
        yy = y - s * 0.75 + row * s * 0.36
        w = s * 0.62 * math.sqrt(max(0.05, 1 - ((yy - y) / s) ** 2))
        for j in range(-1, 2):
            bx = x + j * w * 0.6 + (row % 2) * w * 0.3 - w * 0.15
            bm = k.Icon.intersect(k.ell(icon, bx, yy, w * 0.42, s * 0.26), body)
            k.rfill(icon, bm, (bx - w * 0.2, yy - s * 0.15), s * 0.4,
                    ((0, (240, 240, 240)), (0.6, (170, 170, 170)), (1, (90, 90, 90))), noise=0.06)
            icon.overlay(lambda d, bx=bx, yy=yy, w=w: d.arc((bx - w * 0.42, yy - s * 0.26, bx + w * 0.42, yy + s * 0.26),
                                                           10, 170, fill=(40, 40, 40, 190), width=4), body)
    k.contour(icon, body, 5)


def _bine(icon, sx, mirror, k):
    # hop pole, leaning out a little
    k.rod(icon, (sx(170), 990), (sx(132), 120), 30, (120, 120, 120))
    k.ball(icon, sx(132), 116, 20, (180, 180, 180))
    # the bine winding up the pole
    pts = []
    for i in range(80):
        t = i / 79
        y = 960 - t * 800
        x = 170 - t * 38 + 46 * math.sin(t * 5 * math.pi)
        pts.append((sx(x), y))
    sm = k.line_mask(icon, pts, 16)
    icon.fill(sm, (190, 190, 190), (110, 110, 110))
    k.contour(icon, sm, 4)
    out = -1 if not mirror else 1
    for (i, side, ln) in ((12, -1, 140), (28, 1, 150), (44, -1, 128), (60, 1, 124)):
        x, y = pts[i]
        ang = (200 if side < 0 else 330) if not mirror else (340 if side < 0 else 210)
        _hop_leaf(icon, k, (x, y), ang, ln)
    for i, s in ((22, 62), (38, 58), (54, 54), (70, 46)):
        x, y = pts[i]
        hx = x + out * 60
        icon.line([(x, y), (hx, y + s * 0.5)], 6, (60, 60, 60, 255))
        _cone(icon, k, hx, y + s * 1.3, s)


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _bine(ic, sx, mirror, k))


def charge(icon, k):
    wood = (150, 98, 54)
    x0, x1, y0, y1 = 396, 600, 352, 720
    body = [(x0 + 10, y0), (x1 - 10, y0), (x1 + 6, y1), (x0 - 6, y1)]
    # handle on the right
    h = k.bezier((x1 - 4, 420), (x1 + 120, 410), (x1 + 120, 640), (x1 + 4, 640), 24)
    hm = k.line_mask(icon, h, 36)
    icon.fill(hm, (140, 90, 50), (70, 42, 20), (400, 640))
    k.contour(icon, hm)
    m = icon.poly_mask(body)
    k.dfill(icon, m, (x0, 0), (1, 0), x1 - x0,
            ((0, (110, 70, 38)), (0.2, (196, 140, 86)), (0.5, wood), (0.85, (90, 56, 28)), (1, (60, 36, 18))))
    for i in range(1, 6):  # staves
        x = x0 + (x1 - x0) * i / 6
        icon.line([(x, y0 + 4), (x + (x - 498) * 0.04, y1 - 4)], 4, (50, 30, 14, 170))
    for y in (400, 650):  # iron hoops
        hoop = icon.mask("rectangle", (x0 - 8, y - 16, x1 + 8, y + 16))
        hoop = k.Icon.intersect(hoop, icon.poly_mask([(x0 - 6, y0), (x1 + 6, y0), (x1 + 10, y1), (x0 - 10, y1)]))
        k.dfill(icon, hoop, (x0, 0), (1, 0), x1 - x0,
                ((0, (60, 60, 64)), (0.25, (180, 182, 186)), (0.6, (100, 100, 106)), (1, (40, 40, 44))))
        k.contour(icon, hoop, 4)
    k.contour(icon, m)
    # foam: a heaped cap spilling over the rim with drips
    foam = k.union(*[k.ell(icon, x, y, r) for x, y, r in
                     ((420, 340, 44), (470, 312, 52), (530, 304, 56), (584, 330, 46), (612, 354, 30), (392, 364, 28),
                      (500, 352, 60))])
    foam = k.union(foam, icon.mask("rounded_rectangle", (582, 340, 610, 420), radius=14),
                   icon.mask("rounded_rectangle", (410, 350, 436, 400), radius=12))
    k.rfill(icon, foam, (460, 280), 190, ((0, (255, 255, 250)), (0.5, (240, 232, 210)), (1, (190, 172, 140))),
            noise=0.1)
    for x, y, r in ((470, 320, 8), (520, 330, 6), (560, 316, 7), (440, 350, 5)):
        icon.overlay(lambda d, x=x, y=y, r=r: d.ellipse((x - r, y - r, x + r, y + r), outline=(170, 150, 110, 200),
                                                         width=3))
    k.contour(icon, foam)
