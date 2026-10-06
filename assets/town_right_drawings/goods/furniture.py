"""Furniture: a carved walnut high-back chair on a pale blue field; crossed joiner's handsaws behind the shield."""

FIELD = "#5b7fa6"
SEED = 25


def _saw(icon, loc, mirror, k):
    L = k.CROSS_LEN
    # blade: wide at the heel, narrow at the toe, teeth along the outer edge
    blade = [(-80, 380), (70, 380), (60, L - 10), (-30, L), (-60, L - 40)]
    bp = loc(blade)
    m = icon.poly_mask(bp)
    p0, p1 = loc([(-80, 700), (70, 700)])
    k.dfill(icon, m, p0, (p1[0] - p0[0], p1[1] - p0[1]), 150,
            ((0, (140, 140, 140)), (0.3, (236, 236, 236)), (0.6, (176, 176, 176)), (1, (110, 110, 110))), noise=0.08)
    teeth = []
    n = 15
    step = (L - 60 - 380) / n
    for i in range(n):
        v = 380 + step * i
        a = -80 + 20 * (v - 380) / (L - 60 - 380)
        teeth += [(a, v), (a - 28, v + step * 0.8)]
    tm = icon.poly_mask(loc([(-80, 380)] + teeth + [(-60, L - 40)]))
    icon.fill(tm, (150, 150, 150), (90, 90, 90))
    k.contour(icon, k.union(m, tm))
    # split nuts and the closed handle
    for v in (400, 440):
        p = loc([(0, v)])[0]
        k.ball(icon, p[0], p[1], 10, (230, 230, 230), edge=False)
    handle = loc([(-70, 400), (70, 400), (80, 330), (64, 190), (40, 170), (-40, 170), (-80, 220), (-74, 330)])
    hm = icon.poly_mask(handle)
    hole = icon.poly_mask(loc([(-36, 350), (40, 350), (40, 236), (-30, 236)]))
    hm = k.subtract(hm, hole)
    a, b = loc([(-80, 300), (80, 300)])
    k.cyl(icon, hm, a, b, 160, (120, 120, 120))
    k.contour(icon, hm)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _saw(ic, loc, mirror, k))


def charge(icon, k):
    wood = (128, 78, 42)
    # back legs / posts with finials
    for x in (408, 616):
        k.rod(icon, (x, 250), (x, 740), 30, (110, 66, 36), caps=False)
        k.ball(icon, x, 236, 22, (140, 90, 50))
    # carved back: crest rail with a cartouche, panel with an arch
    crest = [(400, 270), (450, 248), (512, 226), (574, 248), (624, 270), (624, 312), (400, 312)]
    k.block(icon, crest, wood)
    panel = icon.mask("rectangle", (424, 312, 600, 494))
    icon.fill(panel, (120, 72, 38), (70, 40, 20), (312, 494))
    arch = k.union(icon.mask("ellipse", (446, 330, 578, 420)), icon.mask("rectangle", (446, 375, 578, 476)))
    icon.fill(arch, (82, 48, 24), (130, 80, 44), (330, 476))
    k.tint(icon, icon.mask("rectangle", (446, 330, 470, 476)), arch, (0, 0, 0), 0.3, blur=6)
    k.ball(icon, 512, 380, 16, (160, 110, 60))
    k.contour(icon, panel)
    k.contour(icon, arch, 5)
    # seat seen from a little above, with a cushion of red leather
    seat_top = [(392, 486), (632, 486), (668, 538), (356, 538)]
    k.block(icon, seat_top, (150, 52, 40), light=1.4)
    for x in (420, 470, 520, 570, 620):
        k.ball(icon, x + (x - 512) * 0.12, 530, 7, (220, 180, 90), edge=False)
    apron = [(356, 538), (668, 538), (668, 580), (356, 580)]
    k.block(icon, apron, wood)
    # turned front legs and a stretcher
    for x in (376, 648):
        for y0, y1, w in ((580, 622, 34), (622, 650, 46), (650, 710, 30), (710, 736, 42)):
            k.rod(icon, (x, y0), (x, y1), w, wood)
    k.rod(icon, (376, 692), (648, 692), 20, (100, 60, 30))
    k.rod(icon, (408, 680), (616, 680), 14, (90, 54, 28))
