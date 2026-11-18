"""Paper: a fan of deckle-edged handmade sheets, the top one showing laid lines, a watermark and a lifted corner,
on an olive field; crossed pulp paddles from the papermaker's vat behind the shield."""

import math

FIELD = "#4c5a2a"
SEED = 37


def _paddle(icon, loc, mirror, k):
    L = k.CROSS_LEN
    # shaft with a cross grip at the butt
    k.rod(icon, *loc([(0, 30), (0, 840)]), 36, (140, 140, 140))
    k.rod(icon, *loc([(-66, 30), (66, 30)]), 38, (176, 176, 176))
    # long rounded blade, slotted so the pulp runs through
    side = k.bezier((22, 780), (92, 830), (92, 900), (88, 980), 12) + k.bezier((88, 980), (84, 1060), (46, L), (0, L), 12)
    m = icon.poly_mask(loc(side + [(-a, v) for a, v in side[::-1]]))
    for a in (-34, 34):
        m = k.subtract(m, k.line_mask(icon, loc([(a, 880), (a, 1010)]), 24))
    p0, p1 = loc([(0, 780), (0, L)])
    k.cyl(icon, m, p0, p1, 184, (196, 196, 196), spec=1.4)
    k.contour(icon, m)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _paddle(ic, loc, mirror, k))


def _deckle(icon, corners, step=20, amp=6):
    """The corners joined by the torn, uneven edge of a sheet lifted from the mould."""
    out = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        for i in range(n):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t + icon.random.uniform(-amp, amp),
                        a[1] + (b[1] - a[1]) * t + icon.random.uniform(-amp, amp)))
    return out


def _sheet(icon, k, cx, cy, w, h, degrees, stops):
    corners = k.rotated([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)], (cx, cy), degrees)
    m = icon.poly_mask(_deckle(icon, corners))
    k.dfill(icon, m, corners[0], (1, 1.25), math.hypot(w, h), stops, noise=0.05, chroma=0.02)
    k.contour(icon, m, 7)
    return m


def charge(icon, k):
    back = ((0, (240, 228, 198)), (1, (186, 168, 130)))
    _sheet(icon, k, 466, 462, 230, 360, -13, back)
    _sheet(icon, k, 558, 462, 230, 360, 13, back)
    # the top sheet, its lower right corner cut away where it lifts
    x0, y0, x1, y1 = 388, 240, 636, 690
    fold = 92
    sheet = _deckle(icon, [(x0, y0), (x1, y0), (x1, y1 - fold), (x1 - fold, y1), (x0, y1)], 20, 5)
    m = icon.poly_mask(sheet)
    k.dfill(icon, m, (x0, y0), (1, 1.3), 620, ((0, (255, 253, 242)), (0.6, (250, 242, 220)), (1, (226, 212, 180))),
            noise=0.04, chroma=0.02)

    def laid(d):
        for y in range(y0 + 10, y1, 16):  # the fine laid lines of the mould's wires
            d.line([(x0, y), (x1, y)], fill=(150, 130, 92, 46), width=2)
        for x in range(x0 + 41, x1, 83):  # and its wider chain lines
            d.line([(x, y0), (x, y1)], fill=(140, 120, 84, 80), width=4)

    icon.overlay(laid, m)

    # watermark: an orb under a cross, the papermaker's mark held up to the light
    mark = (128, 104, 64, 235)

    def watermark(d):
        cx, cy = 512, 478
        d.ellipse((cx - 64, cy - 64, cx + 64, cy + 64), outline=mark, width=14)
        d.line([(cx - 64, cy), (cx + 64, cy)], fill=mark, width=12)
        d.line([(cx, cy), (cx, cy + 64)], fill=mark, width=12)
        d.line([(cx, cy - 64), (cx, cy - 164)], fill=mark, width=14)
        d.line([(cx - 40, cy - 124), (cx + 40, cy - 124)], fill=mark, width=14)

    icon.overlay(watermark, m)
    k.contour(icon, m, 7)

    # the lifted corner, folded back over the sheet, its shadow on the page below
    flap = [(x1, y1 - fold), (x1 - fold, y1), (x1 - fold - 10, y1 - fold - 10)]
    k.tint(icon, icon.poly_mask([(p[0] - 16, p[1] - 16) for p in flap]), m, (50, 36, 16), 0.5, blur=10)
    fm = icon.poly_mask(flap)
    k.dfill(icon, fm, flap[2], (1, 1), fold * 1.3, ((0, (255, 248, 228)), (1, (176, 156, 116))), noise=0.04, chroma=0.02)
    k.contour(icon, fm, 7)
