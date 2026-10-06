"""Naval supplies: an iron anchor with a wooden stock, fouled with a hemp cable, on a sea-blue field; crossed
boathooks behind the shield."""

FIELD = "#2f6a78"
SEED = 36


def _boathook(icon, loc, mirror, k):
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 0), (0, L - 170)]), 32, (120, 120, 120))
    k.rod(icon, *loc([(0, L - 230), (0, L - 160)]), 42, (180, 180, 180), caps=False)  # socket
    spike = loc([(-16, L - 170), (16, L - 170), (6, L - 20), (0, L + 30), (-6, L - 20)])
    k.block(icon, spike, (210, 210, 210))
    hook = k.bezier((10, L - 150), (110, L - 150), (130, L - 40), (70, L - 10), 20)
    hm = k.line_mask(icon, loc(hook), 30)
    a, b = loc([(10, L - 100), (130, L - 100)])
    k.cyl(icon, hm, a, b, 130, (200, 200, 200))
    k.contour(icon, hm)
    tip = loc([(66, L - 10)])[0]
    k.ball(icon, tip[0], tip[1], 14, (220, 220, 220), edge=False)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _boathook(ic, loc, mirror, k))


def charge(icon, k):
    cx = 512
    iron = (92, 96, 104)
    # arms and flukes
    for s in (-1, 1):
        arm = k.bezier((cx, 716), (cx + s * 90, 712), (cx + s * 150, 660), (cx + s * 164, 572), 20)
        am = k.line_mask(icon, arm, 54)
        k.dfill(icon, am, (cx - 170, 560), (1, 1), 300,
                ((0, (170, 174, 182)), (0.5, iron), (1, (40, 42, 48))), noise=0.12)
        k.contour(icon, am)
        fx, fy = cx + s * 164, 572
        fluke = [(fx, fy - 96), (fx + s * 58, fy + 10), (fx + s * 14, fy + 40), (fx - s * 30, fy + 26)]
        k.block(icon, fluke, (120, 124, 132))
    # shank
    shank = [(cx - 30, 300), (cx + 30, 300), (cx + 38, 720), (cx - 38, 720)]
    k.block(icon, shank, iron, light=1.6)
    # crown
    k.ball(icon, cx, 716, 40, (110, 114, 122))
    # ring at the top
    ring = k.subtract(k.ell(icon, cx, 250, 58), k.ell(icon, cx, 250, 32))
    k.dfill(icon, ring, (cx - 50, 204), (1, 1), 140, ((0, (190, 194, 200)), (0.5, iron), (1, (40, 42, 48))))
    k.contour(icon, ring)
    k.contour(icon, k.ell(icon, cx, 250, 32), 5)
    # wooden stock across the top of the shank, with iron bands
    stock = icon.mask("rounded_rectangle", (cx - 170, 312, cx + 170, 372), radius=26)
    k.cyl(icon, stock, (cx - 170, 342), (cx + 170, 342), 60, (138, 92, 52))
    for x in (cx - 120, cx + 120):
        k.rod(icon, (x, 310), (x, 374), 14, (80, 80, 86))
    k.contour(icon, stock)
    # hemp cable from the ring, round the shank, trailing down
    cable = k.bezier((cx + 40, 270), (cx + 160, 300), (cx + 120, 420), (cx - 10, 430), 16)
    cable += k.bezier((cx - 10, 430), (cx - 150, 450), (cx - 140, 540), (cx + 10, 540), 16)[1:]
    cable += k.bezier((cx + 10, 540), (cx + 130, 550), (cx + 100, 640), (cx + 40, 660), 12)[1:]
    k.rope(icon, cable, 34, (196, 160, 104))
