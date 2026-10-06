"""Fine cloth: a bolt of purple silk unrolled into a crimson brocade drape with a gold fringe, on a cream
field; tasselled curtains hang behind the shield on both sides."""

FIELD = "#e2d6bc"
SEED = 22


def _curtain(icon, sx, mirror, k):
    top = [(sx(330), 130), (sx(250), 116), (sx(150), 128), (sx(100), 166)]
    outer = k.bezier((sx(100), 166), (sx(60), 300), (sx(140), 430), (sx(126), 520), 16)
    flare = k.bezier((sx(126), 520), (sx(90), 640), (sx(50), 760), (sx(60), 880), 16)
    hem = [(sx(110), 905), (sx(170), 884), (sx(230), 908), (sx(290), 872), (sx(330), 840)]
    pts = top + outer[1:] + flare[1:] + hem + [(sx(330), 520)]
    m = icon.poly_mask(pts)
    # vertical folds: alternating light and dark bands across the curtain
    x_lo, x_hi = (40, 340)
    stops = []
    for i in range(9):
        t = i / 8
        v = (200, 200, 200) if i % 2 == 0 else (90, 90, 90)
        stops.append((t, v))
    k.dfill(icon, m, (sx(x_lo), 0), (1 if not mirror else -1, 0.12), x_hi - x_lo, stops, noise=0.10)
    k.tint(icon, icon.mask("rectangle", (0, 470, 1024, 560)), m, (0, 0, 0), 0.35, blur=20)
    k.contour(icon, m)
    # tie-back cord and tassel
    k.rope(icon, [(sx(100), 520), (sx(170), 530), (sx(270), 520)], 22, (190, 190, 190))
    k.ball(icon, sx(108), 560, 28, (200, 200, 200))
    tassel = [(sx(90), 580), (sx(126), 580), (sx(142), 690), (sx(74), 690)]
    tm = icon.poly_mask(tassel)
    icon.fill(tm, (210, 210, 210), (90, 90, 90), (580, 690))
    for x in range(78, 142, 12):
        icon.line([(sx(x + 6), 600), (sx(x + 2), 688)], 4, (40, 40, 40, 150))
    k.contour(icon, tm)


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _curtain(ic, sx, mirror, k))


def charge(icon, k):
    # the hanging silk, gathered in towards the bottom, with deep folds
    drape = [(372, 318), (652, 318), (640, 520), (612, 700), (590, 712), (560, 700), (532, 716), (504, 702),
             (476, 716), (448, 700), (420, 712), (408, 690), (384, 520)]
    m = icon.poly_mask(drape)
    stops = []
    for i, t in enumerate((0, 0.09, 0.2, 0.31, 0.43, 0.55, 0.66, 0.78, 0.9, 1.0)):
        stops.append((t, (196, 52, 64) if i % 2 else (112, 18, 34)))
    k.dfill(icon, m, (372, 0), (1, 0), 280, stops, noise=0.08)
    k.tint(icon, icon.mask("rectangle", (300, 300, 760, 380)), m, (0, 0, 0), 0.4, blur=18)
    # brocade: small gold flowers in a lattice
    for row, y in enumerate(range(400, 690, 62)):
        for x in range(408 + (row % 2) * 34, 640, 68):
            fm = k.ell(icon, x, y, 11, 13)
            k.tint(icon, fm, m, (236, 190, 80), 0.85)
            k.tint(icon, k.ell(icon, x - 3, y - 4, 4), m, (255, 245, 200), 0.8)
    k.contour(icon, m)
    # gold fringe along the hem
    def fringe(d):
        for i in range(0, 260, 9):
            x = 406 + i * 0.75 + 12
            y = 708 + (8 if (i // 28) % 2 else 0)
            d.line([(x, y - 6), (x - 2, y + 34)], fill=(222, 172, 60, 255), width=5)
            d.line([(x + 3, y - 4), (x + 1, y + 30)], fill=(120, 80, 20, 200), width=2)
    icon.overlay(fringe)
    # the roll of purple silk the drape comes off
    roll = icon.mask("rounded_rectangle", (342, 262, 682, 344), radius=40)
    k.cyl(icon, roll, (342, 303), (682, 303), 82, (104, 50, 128))
    for x in (362, 662):
        icon.overlay(lambda d, x=x: d.arc((x - 24, 264, x + 24, 342), 90, 270 if x < 500 else 450,
                                          fill=(40, 16, 50, 200), width=4))
    k.contour(icon, roll)
    k.ball(icon, 342, 303, 26, (220, 176, 70))
    k.ball(icon, 682, 303, 26, (220, 176, 70))
