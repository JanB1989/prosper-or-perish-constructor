"""Porcelain: a blue-and-white lidded ginger jar with a lotus scroll on an ochre field; crossed painter's
brushes (bamboo handles, ink-laden tips) behind the shield."""

import math

FIELD = "#b8863a"
SEED = 28


def _brush(icon, loc, mirror, k):
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 60), (0, L - 200)]), 44, (150, 150, 150))
    for v in range(220, L - 220, 170):  # bamboo nodes
        k.rod(icon, *loc([(0, v), (0, v + 14)]), 46, (200, 200, 200))
    k.rod(icon, *loc([(0, L - 210), (0, L - 160)]), 50, (210, 210, 210))  # ferrule
    tuft = k.bezier((-40, L - 180), (-84, L - 90), (-30, L - 10), (0, L + 30), 14) + \
        k.bezier((0, L + 30), (30, L - 10), (84, L - 90), (40, L - 180), 14)[1:]
    m = icon.poly_mask(loc(tuft))
    a, b = loc([(-70, L - 100), (70, L - 100)])
    k.cyl(icon, m, a, b, 140, (90, 90, 90))
    k.contour(icon, m)
    # knob at the butt
    p = loc([(0, 50)])[0]
    k.ball(icon, p[0], p[1], 30, (200, 200, 200))


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _brush(ic, loc, mirror, k))


def charge(icon, k):
    cx = 512
    cobalt = (34, 62, 150)
    # body: high rounded shoulder, tapering to the foot
    prof = [(0, 84), (0.06, 104), (0.2, 160), (0.36, 172), (0.55, 156), (0.78, 118), (0.93, 96), (1, 100)]
    y0, y1 = 326, 770
    right = [(cx + w, y0 + (y1 - y0) * t) for t, w in prof]
    pts = right + [(2 * cx - x, y) for x, y in right[::-1]]
    m = icon.poly_mask(pts)
    k.rfill(icon, m, (cx - 70, 440), 300,
            ((0, (252, 252, 250)), (0.35, (232, 236, 238)), (0.75, (170, 182, 196)), (1, (108, 120, 140))), noise=0.06,
            chroma=0.02)
    # blue decoration: shoulder band of lappets, lotus scroll, foot band
    def deco(d):
        col = cobalt + (235,)
        d.line([(cx - 150, 392), (cx + 150, 392)], fill=col, width=8)
        for x in range(cx - 140, cx + 141, 40):
            d.polygon([(x - 18, 396), (x + 18, 396), (x, 440)], fill=col)
        ys = [560 + 46 * math.sin((x - cx) / 40) for x in range(cx - 170, cx + 171, 6)]
        pts_ = list(zip(range(cx - 170, cx + 171, 6), ys))
        d.line(pts_, fill=col, width=9, joint="curve")
        for i, (x, y) in enumerate(pts_[::9]):
            s = 1 if i % 2 else -1
            d.ellipse((x - 20, y + s * 34 - 14, x + 20, y + s * 34 + 14), fill=col)
            d.ellipse((x - 8, y + s * 34 - 6, x + 8, y + s * 34 + 6), fill=(230, 236, 246, 255))
        d.line([(cx - 130, 690), (cx + 130, 690)], fill=col, width=8)
        d.line([(cx - 120, 712), (cx + 120, 712)], fill=col, width=5)
        for x in range(cx - 110, cx + 111, 24):
            d.line([(x, 718), (x, 752)], fill=col, width=6)
    icon.overlay(deco, m)
    k.tint(icon, icon.mask("rectangle", (cx + 60, 300, cx + 200, 800)), m, (40, 60, 100), 0.30, blur=30)
    icon.overlay(lambda d: d.line(k.bezier((cx - 120, 420), (cx - 138, 480), (cx - 126, 560), (cx - 100, 620), 10),
                                  fill=(255, 255, 255, 200), width=12, joint="curve"))
    k.contour(icon, m)
    # domed lid with a knob
    lid = k.union(icon.mask("ellipse", (cx - 106, 270, cx + 106, 350)), icon.mask("rectangle", (cx - 106, 310, cx + 106, 336)))
    k.rfill(icon, lid, (cx - 40, 286), 160, ((0, (252, 252, 250)), (0.6, (210, 218, 228)), (1, (120, 132, 150))),
            noise=0.05)
    icon.overlay(lambda d: d.line([(cx - 104, 330), (cx + 104, 330)], fill=cobalt + (230,), width=8), lid)
    k.contour(icon, lid)
    k.ball(icon, cx, 266, 26, (236, 240, 246))
    icon.overlay(lambda d: d.ellipse((cx - 12, 254, cx + 12, 278), fill=cobalt + (220,)))
