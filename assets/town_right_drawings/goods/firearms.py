"""Firearms: a matchlock arquebus laid diagonally, its smouldering match in the serpentine, on a slate field;
powder horns hang on cords at both sides of the shield."""

import math

FIELD = "#e2d6bc"
SEED = 34


def _horn(icon, sx, mirror, k):
    # cord from the top corner of the shield
    k.rope(icon, [(sx(300), 200), (sx(170), 260), (sx(120), 330)], 12, (180, 180, 180))
    k.rope(icon, [(sx(300), 200), (sx(220), 420), (sx(200), 760)], 12, (180, 180, 180))
    # horn: wide at the base cap (top), curving down to a narrow capped tip
    spine = k.bezier((sx(126), 340), (sx(52), 520), (sx(80), 760), (sx(220), 850), 30)
    left, right = [], []
    for i, (x, y) in enumerate(spine):
        t = i / (len(spine) - 1)
        w = 72 * (1 - t) + 16 * t
        if i < len(spine) - 1:
            dx, dy = spine[i + 1][0] - x, spine[i + 1][1] - y
        n = math.hypot(dx, dy) or 1
        px, py = -dy / n, dx / n
        left.append((x + px * w, y + py * w))
        right.append((x - px * w, y - py * w))
    m = icon.poly_mask(left + right[::-1])
    k.rfill(icon, m, (sx(80), 420), 460, ((0, (240, 240, 240)), (0.4, (170, 170, 170)), (0.8, (90, 90, 90)),
                                         (1, (60, 60, 60))), noise=0.14)
    for i in (6, 20):
        a, b = left[i], right[i]
        k.rod(icon, a, b, 22, (200, 200, 200))
    k.contour(icon, m)
    k.block(icon, [left[0], right[0], (right[0][0] + (right[0][0] - left[0][0]) * 0.0, right[0][1] - 40),
                   (left[0][0], left[0][1] - 40)], (190, 190, 190))
    k.ball(icon, spine[-1][0], spine[-1][1], 20, (200, 200, 200))


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _horn(ic, sx, mirror, k))


def charge(icon, k):
    org, ang = (318, 676), -42  # butt plate at the lower left, muzzle to the upper right

    def P(pts):
        return k.rotated([(x * 1.18, y * 1.18) for x, y in pts], org, ang)

    walnut = (128, 74, 40)
    # stock: angular butt with a straight comb, slim wrist, long forestock
    stock = P([(0, -34), (150, -14), (410, -8), (420, 6), (410, 16), (190, 20), (150, 24), (0, 66)])
    sm = icon.poly_mask(stock)
    a, b = P([(150, -40), (150, 66)])
    k.dfill(icon, sm, a, (b[0] - a[0], b[1] - a[1]), 106,
            ((0, (200, 140, 86)), (0.35, walnut), (1, (58, 30, 12))), noise=0.16)
    k.strokes(icon, sm, (40, 20, 8), 50, ang, 9, 2, 0.5, (20, 60))
    k.contour(icon, sm)
    k.block(icon, P([(0, -34), (10, -34), (10, 66), (0, 66)]), (60, 60, 64))  # butt plate
    # barrel on top, longer than the stock
    barrel = P([(120, -36), (520, -28), (520, -8), (120, -10)])
    bm = icon.poly_mask(barrel)
    a, b = P([(300, -36), (300, -8)])
    k.dfill(icon, bm, a, (b[0] - a[0], b[1] - a[1]), 28,
            ((0, (90, 94, 102)), (0.3, (200, 204, 212)), (0.6, (92, 96, 104)), (1, (36, 38, 42))), noise=0.08)
    k.contour(icon, bm)
    k.block(icon, P([(500, -40), (522, -40), (522, -4), (500, -4)]), (150, 154, 160))  # muzzle ring
    k.block(icon, P([(470, -46), (480, -46), (480, -36), (470, -36)]), (170, 170, 176), edge=False)  # sight
    for x in (280, 380):
        k.block(icon, P([(x, -40), (x + 14, -40), (x + 14, 18), (x, 18)]), (190, 194, 200))
    # lock plate, serpentine with the match, trigger guard
    k.block(icon, P([(130, -12), (220, -12), (220, 12), (130, 12)]), (176, 180, 186))
    serp = k.bezier(*P([(200, 6), (176, 40), (140, -50), (176, -64)]), 16)
    s2 = k.line_mask(icon, serp, 16)
    icon.fill(s2, (214, 216, 222), (110, 114, 120))
    k.contour(icon, s2, 4)
    guard = k.bezier(*P([(150, 22), (150, 64), (220, 64), (230, 20)]), 14)
    gm = k.line_mask(icon, guard, 12)
    icon.fill(gm, (190, 194, 200), (100, 104, 110))
    k.contour(icon, gm, 4)
    k.rod(icon, *P([(186, 22), (180, 50)]), 10, (200, 204, 210), edge=False)
    tip = P([(178, -72)])[0]
    icon.overlay(lambda d: d.line(k.bezier(tip, (tip[0] - 20, tip[1] - 50), (tip[0] + 40, tip[1] - 80),
                                            (tip[0] + 10, tip[1] - 140), 16), fill=(230, 230, 220, 140), width=10,
                                  joint="curve"))
    k.ball(icon, tip[0], tip[1], 12, (255, 140, 40), edge=False)
