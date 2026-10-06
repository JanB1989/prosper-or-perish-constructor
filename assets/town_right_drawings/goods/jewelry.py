"""Jewelry: a gold ring set with a faceted ruby on a sable field; strings of pearls with pendant drops hang
on both sides of the shield."""

import math

FIELD = "#26262c"
SEED = 27


def _pearl_string(icon, sx, mirror, k):
    path = k.bezier((sx(300), 190), (sx(30), 210), (sx(10), 560), (sx(150), 760), 40)
    k.pearls(icon, path, 25, (205, 205, 205), gap=1.85)
    inner = k.bezier((sx(300), 330), (sx(140), 360), (sx(110), 520), (sx(200), 610), 30)
    k.pearls(icon, inner, 19, (190, 190, 190), gap=1.9)
    # pendant drop: a mounted stone below the lower end
    x, y = sx(160), 820
    k.ball(icon, x, y - 34, 18, (180, 180, 180))
    drop = [(x, y - 20), (x + 40, y + 30), (x + 26, y + 90), (x, y + 112), (x - 26, y + 90), (x - 40, y + 30)]
    k.block(icon, drop, (190, 190, 190), light=1.5)
    k.tint(icon, icon.poly_mask([(x - 30, y + 20), (x, y - 10), (x, y + 60)]), icon.poly_mask(drop),
           (255, 255, 255), 0.4)


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _pearl_string(ic, sx, mirror, k))


def charge(icon, k):
    cx, cy = 512, 560
    gold = ((0, (255, 240, 170)), (0.3, (236, 184, 64)), (0.65, (170, 110, 24)), (1, (90, 52, 10)))
    outer = icon.mask("ellipse", (cx - 172, cy - 176, cx + 172, cy + 176))
    inner = icon.mask("ellipse", (cx - 122, cy - 118, cx + 122, cy + 134))
    band = k.subtract(outer, inner)
    k.rfill(icon, band, (cx - 120, cy - 110), 360, gold, noise=0.08)
    # rounded band: bright inner edge at the lower right, dark under the top
    k.tint(icon, k.subtract(icon.mask("ellipse", (cx - 132, cy - 128, cx + 132, cy + 144)), inner), band,
           (60, 30, 4), 0.5, blur=4)
    icon.overlay(lambda d: d.arc((cx - 158, cy - 162, cx + 158, cy + 162), 150, 250, fill=(255, 250, 210, 200), width=10))
    k.contour(icon, outer)
    k.contour(icon, k.subtract(icon.mask("rectangle", (0, 0, 1024, 1024)), inner), 6)
    # claw setting on top
    bez = [(cx - 96, cy - 150), (cx + 96, cy - 150), (cx + 70, cy - 210), (cx - 70, cy - 210)]
    k.block(icon, bez, (220, 160, 50), light=1.35)
    for s in (-1, 1):
        k.rod(icon, (cx + s * 74, cy - 214), (cx + s * 86, cy - 280), 18, (236, 184, 64))
    # ruby: faceted cushion cut seen from the front
    gx, gy, r = cx, cy - 262, 92
    oct_ = [(gx + r * math.cos(math.radians(a)), gy + r * 0.82 * math.sin(math.radians(a))) for a in range(-180, 180, 45)]
    gm = icon.poly_mask(oct_)
    k.rfill(icon, gm, (gx - 30, gy - 30), 140, ((0, (255, 120, 130)), (0.4, (200, 24, 44)), (1, (80, 0, 14))))
    table = [(gx + r * 0.48 * math.cos(math.radians(a)), gy + r * 0.4 * math.sin(math.radians(a)))
             for a in range(-180, 180, 45)]
    k.tint(icon, icon.poly_mask(table), gm, (255, 90, 110), 0.45)
    for (ax, ay), (bx, by) in zip(oct_, table):
        icon.line([(ax, ay), (bx, by)], 3, (90, 0, 20, 200))
    icon.outline(table, 3, (110, 10, 30, 200))
    k.tint(icon, icon.poly_mask([oct_[0], oct_[1], oct_[2], table[2], table[1], table[0]]), gm, (255, 255, 255), 0.35)
    k.contour(icon, gm)
    # sparkle
    def star(d):
        x, y = gx - 40, gy - 36
        d.line([(x - 24, y), (x + 24, y)], fill=(255, 255, 255, 230), width=5)
        d.line([(x, y - 24), (x, y + 24)], fill=(255, 255, 255, 230), width=5)
    icon.overlay(star)
