"""Weaponry: two crossed swords, points up, with gilt hilts on a dark azure field; crossed halberds behind
the shield."""

FIELD = "#263f6e"
SEED = 33


def _halberd(icon, loc, mirror, k):
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 0), (0, L - 160)]), 38, (110, 110, 110))
    # langets
    k.rod(icon, *loc([(0, L - 330), (0, L - 160)]), 40, (170, 170, 170), caps=False)
    # top spike
    spike = loc([(-28, L - 190), (28, L - 190), (12, L - 40), (0, L + 40), (-12, L - 40)])
    k.block(icon, spike, (210, 210, 210))
    # axe blade with a curved edge, on the outer side
    axe = loc([(10, L - 300), (70, L - 310), (190, L - 370), (220, L - 270), (222, L - 180), (196, L - 80),
               (70, L - 160), (10, L - 170)])
    m = icon.poly_mask(axe)
    p0, p1 = loc([(10, L - 240), (222, L - 240)])
    k.dfill(icon, m, p0, (p1[0] - p0[0], p1[1] - p0[1]), 212,
            ((0, (120, 120, 120)), (0.5, (200, 200, 200)), (0.85, (250, 250, 250)), (1, (160, 160, 160))))
    k.contour(icon, m)
    # back hook
    hook = loc([(-14, L - 290), (-14, L - 210), (-80, L - 236), (-140, L - 190), (-110, L - 270)])
    k.block(icon, hook, (180, 180, 180))


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _halberd(ic, loc, mirror, k))


def _sword(icon, k, mirror):
    s = -1 if mirror else 1
    # local: along from the pommel (0) to the point (560); rotated so the point goes up and outwards
    ang = -90 + s * 36
    org = (512 - s * 150, 730)

    def P(pts):
        return k.rotated(pts, org, ang)

    blade = P([(130, -36), (480, -26), (590, 0), (480, 26), (130, 36)])
    m = icon.poly_mask(blade)
    a, b = P([(300, -36), (300, 36)])
    k.dfill(icon, m, a, (b[0] - a[0], b[1] - a[1]), 72,
            ((0, (150, 158, 170)), (0.35, (246, 248, 250)), (0.55, (190, 196, 206)), (1, (96, 102, 114))), noise=0.06)
    icon.line(P([(140, 0), (450, 0)]), 6, (90, 96, 110, 190))
    k.contour(icon, m)
    gold = (226, 172, 58)
    k.rod(icon, *P([(40, 0), (120, 0)]), 40, (110, 60, 36))  # grip
    for x in (60, 80, 100):
        icon.line(P([(x, -15), (x + 8, 15)]), 4, (60, 30, 16, 200))
    k.rod(icon, *P([(122, -104), (122, 104)]), 36, gold)  # crossguard
    for y in (-104, 104):
        q = P([(116, y)])[0]
        k.ball(icon, q[0], q[1], 24, gold)
    q = P([(26, 0)])[0]
    k.ball(icon, q[0], q[1], 40, gold)  # pommel


def charge(icon, k):
    _sword(icon, k, False)
    _sword(icon, k, True)
