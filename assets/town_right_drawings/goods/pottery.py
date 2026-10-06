"""Pottery: a terracotta amphora with a black painted band on a cream field; a jug and a lidded jar stand
on either side below the shield."""

import math

FIELD = "#e2d6bc"
SEED = 24


def _profile(cx, y0, y1, widths):
    """Closed vessel outline from (t, half-width) pairs, t from 0 (top) to 1 (bottom)."""
    right = [(cx + w, y0 + (y1 - y0) * t) for t, w in widths]
    left = [(cx - w, y0 + (y1 - y0) * t) for t, w in widths[::-1]]
    return right + left


def _vessel(icon, sx, mirror, k):
    if not mirror:  # tall jug with a spout and handle
        cx = 150
        prof = [(0, 46), (0.06, 40), (0.2, 44), (0.42, 92), (0.62, 100), (0.82, 82), (0.95, 60), (1, 64)]
        pts = _profile(cx, 560, 984, prof)
        handle = k.bezier((cx + 44, 600), (cx + 150, 600), (cx + 150, 760), (cx + 80, 800), 20)
        hm = k.line_mask(icon, handle, 30)
        icon.fill(hm, (200, 200, 200), (80, 80, 80), (600, 800))
        k.contour(icon, hm)
        spout = [(cx - 44, 566), (cx - 96, 544), (cx - 84, 590), (cx - 40, 606)]
    else:  # squat lidded jar
        cx = 140
        prof = [(0, 50), (0.1, 56), (0.3, 104), (0.55, 112), (0.8, 90), (0.95, 64), (1, 66)]
        pts = _profile(cx, 680, 984, prof)
        spout = None
    pts = [(sx(x), y) for x, y in pts]
    m = icon.poly_mask(pts)
    k.rfill(icon, m, (sx(cx - 40), 700 if not mirror else 760), 200,
            ((0, (236, 236, 236)), (0.4, (170, 170, 170)), (0.85, (84, 84, 84)), (1, (60, 60, 60))), noise=0.1)
    for y in ((700, 860) if not mirror else (760, 900)):
        icon.line([(sx(cx - 96), y), (sx(cx + 96), y)], 6, (40, 40, 40, 120))
    k.contour(icon, m)
    if spout:
        sp = [(sx(x), y) for x, y in spout]
        k.block(icon, sp, (190, 190, 190))
    if mirror:  # lid with a knob
        lid = icon.mask("ellipse", (min(sx(cx - 62), sx(cx + 62)), 650, max(sx(cx - 62), sx(cx + 62)), 700))
        icon.fill(lid, (220, 220, 220), (100, 100, 100), (650, 700))
        k.contour(icon, lid)
        k.ball(icon, sx(cx), 640, 22, (200, 200, 200))


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _vessel(ic, sx, mirror, k))


def charge(icon, k):
    cx = 512
    prof = [(0, 52), (0.05, 44), (0.14, 40), (0.22, 60), (0.32, 134), (0.42, 150), (0.56, 140), (0.72, 104),
            (0.86, 56), (0.95, 26), (1, 30)]
    y0, y1 = 252, 776
    pts = _profile(cx, y0, y1, prof)
    # handles from the neck to the shoulder
    for s in (-1, 1):
        h = k.bezier((cx + s * 40, 300), (cx + s * 150, 280), (cx + s * 170, 330), (cx + s * 120, 420), 20)
        hm = k.line_mask(icon, h, 30)
        icon.fill(hm, (196, 108, 64), (110, 50, 24), (280, 420))
        k.contour(icon, hm)
    m = icon.poly_mask(pts)
    k.rfill(icon, m, (cx - 70, 400), 300,
            ((0, (230, 146, 96)), (0.35, (192, 98, 54)), (0.75, (132, 58, 28)), (1, (84, 34, 16))), noise=0.16)
    # black-figure band on the shoulder with a meander of key steps
    band = k.Icon.intersect(m, icon.mask("rectangle", (300, 412, 724, 500)))
    k.tint(icon, band, m, (24, 16, 12), 0.92)
    for x in range(372, 660, 44):
        icon.overlay(lambda d, x=x: d.line([(x, 480), (x, 436), (x + 30, 436), (x + 30, 462), (x + 14, 462)],
                                           fill=(214, 120, 70, 255), width=6), band)
    icon.line([(cx - 120, 520), (cx + 120, 520)], 5, (24, 16, 12, 220))
    icon.line([(cx - 104, 650), (cx + 104, 650)], 5, (24, 16, 12, 200))
    # rim
    rim = icon.mask("ellipse", (cx - 60, 238, cx + 60, 268))
    icon.fill(rim, (214, 130, 84), (120, 54, 26), (238, 268))
    icon.draw.ellipse((cx - 38, 244, cx + 38, 262), fill=(50, 22, 12, 255))
    k.tint(icon, icon.mask("ellipse", (cx - 110, 330, cx - 50, 520)), m, (255, 236, 210), 0.25, blur=16)
    k.contour(icon, k.union(m, rim))
