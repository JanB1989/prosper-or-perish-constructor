"""Lacquerware: a cinnabar-red lacquer box with a black rim and gold decoration on a jade field; open folding
fans spread at both lower sides of the shield."""

import math

FIELD = "#3d7058"
SEED = 29


def _fan(icon, sx, mirror, k):
    px, py = sx(350), 960
    a0, a1 = (192, 282) if not mirror else (258, 348)
    r = 300
    sector = icon.mask("pieslice", (px - r, py - r, px + r, py + r), start=a0, end=a1)
    inner = icon.mask("pieslice", (px - 70, py - 70, px + 70, py + 70), start=a0, end=a1)
    leaf = k.subtract(sector, inner)
    icon.fill(leaf, (220, 220, 220), (130, 130, 130), (py - r, py))
    # pleats: alternating lit and shaded wedges
    n = 12
    for i in range(n):
        if i % 2:
            b0 = a0 + (a1 - a0) * i / n
            b1 = a0 + (a1 - a0) * (i + 1) / n
            k.tint(icon, icon.mask("pieslice", (px - r, py - r, px + r, py + r), start=b0, end=b1), leaf,
                   (0, 0, 0), 0.32)
    # painted border band near the edge
    band = k.subtract(sector, icon.mask("pieslice", (px - r + 46, py - r + 46, px + r - 46, py + r - 46),
                                        start=a0, end=a1))
    k.tint(icon, band, leaf, (60, 60, 60), 0.35)
    k.contour(icon, leaf)
    # guard sticks and rivet
    for a in (a0 + 1, a1 - 1):
        t = math.radians(a)
        k.rod(icon, (px, py), (px + math.cos(t) * (r + 6), py + math.sin(t) * (r + 6)), 18, (110, 110, 110))
    k.ball(icon, px, py, 22, (210, 210, 210))


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _fan(ic, sx, mirror, k))


def charge(icon, k):
    red = (176, 38, 26)
    black = (30, 20, 18)
    # lid top seen from above (trapezoid), lid side, box body, small feet
    top = [(390, 306), (634, 306), (690, 404), (334, 404)]
    lid_side = [(334, 404), (690, 404), (690, 456), (334, 456)]
    body = [(350, 456), (674, 456), (674, 668), (350, 668)]
    for x0 in (360, 624):
        k.block(icon, [(x0, 668), (x0 + 40, 668), (x0 + 34, 706), (x0 + 6, 706)], black)
    bm = k.block(icon, body, red, light=1.3, dark=0.5)
    k.tint(icon, icon.mask("rectangle", (350, 456, 674, 490)), bm, (0, 0, 0), 0.45, blur=10)
    k.block(icon, lid_side, black, light=2.4)
    tm = icon.poly_mask(top)
    k.dfill(icon, tm, (334, 306), (1, 0.4), 420,
            ((0, (230, 90, 60)), (0.4, (186, 44, 30)), (1, (110, 20, 14))), noise=0.08)
    # black inner border on the lid
    inner_top = [(408, 320), (616, 320), (662, 392), (362, 392)]
    icon.outline(inner_top, 7, (30, 20, 18, 230))
    # gold: a roundel flower on the lid, cloud scrolls on the body
    gold = (226, 176, 70, 255)
    def lid_gold(d):
        cx, cy = 512, 356
        d.ellipse((cx - 70, cy - 30, cx + 70, cy + 30), outline=gold, width=6)
        for i in range(8):
            a = math.radians(i * 45)
            d.ellipse((cx + math.cos(a) * 40 - 12, cy + math.sin(a) * 17 - 6, cx + math.cos(a) * 40 + 12,
                       cy + math.sin(a) * 17 + 6), fill=gold)
        d.ellipse((cx - 12, cy - 6, cx + 12, cy + 6), fill=(255, 230, 150, 255))
    icon.overlay(lid_gold, tm)
    def body_gold(d):
        for cx in (430, 594):
            for r in (38, 22):
                d.arc((cx - r, 560 - r, cx + r, 560 + r), 180, 450, fill=gold, width=6)
        d.line([(372, 640), (652, 640)], fill=gold, width=5)
        d.line([(372, 480), (652, 480)], fill=gold, width=4)
        d.arc((468, 520, 556, 610), 200, 340, fill=gold, width=6)
    icon.overlay(body_gold, bm)
    # gloss on the lacquer
    k.tint(icon, icon.poly_mask([(400, 316), (480, 316), (420, 396), (350, 396)]), tm, (255, 230, 220), 0.25, blur=6)
    k.tint(icon, icon.mask("rectangle", (362, 470, 392, 660)), bm, (255, 220, 210), 0.22, blur=6)
    k.contour(icon, k.union(tm, icon.poly_mask(lid_side)))
