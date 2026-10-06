"""Cloth: a stack of folded woollen bolts (madder, woad, undyed) tied with a cord and a lead cloth seal,
on a vert field; crossed cloth-cropping shears behind the shield."""

FIELD = "#3a6440"
SEED = 21


def _shears(icon, loc, mirror, k):
    L = k.CROSS_LEN
    # spring bow at the butt
    bow = k.bezier((-46, 330), (-70, 60), (70, 60), (46, 330), 30)
    m = k.line_mask(icon, loc(bow), 34)
    a, b = loc([(-60, 200), (60, 200)])
    k.cyl(icon, m, a, b, 140, (170, 170, 170))
    k.contour(icon, m)
    # wrapped grips
    for s in (-1, 1):
        k.rod(icon, *loc([(s * 46, 320), (s * 34, 470)]), 40, (110, 110, 110))
    # two long blades, slightly open
    for s in (1, -1):
        blade = loc([(s * 4, 460), (s * 50, 470), (s * 74, 720), (s * 70, L - 90), (s * 30, L + 10), (s * 8, L - 40),
                     (s * 4, 700)])
        bm = icon.poly_mask(blade)
        p0, p1 = loc([(s * 74, 700), (s * 4, 700)])
        k.dfill(icon, bm, p0, (p1[0] - p0[0], p1[1] - p0[1]), 70,
                ((0, (120, 120, 120)), (0.45, (235, 235, 235)), (1, (150, 150, 150))), noise=0.1)
        k.contour(icon, bm)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _shears(ic, loc, mirror, k))


def _bolt(icon, k, x0, y0, x1, y1, color, layers=3):
    """One folded bolt seen from the front and a little from above."""
    top = icon.poly_mask([(x0 + 14, y0), (x1 - 8, y0), (x1, y0 + 18), (x0 + 4, y0 + 18)])
    front = icon.mask("rounded_rectangle", (x0, y0 + 14, x1, y1), radius=22)
    lit, base, dark = k.tones(color, 1.3, 0.45)
    icon.fill(front, lit, dark, (y0 + 10, y1), noise=0.12)
    icon.fill(top, tuple(min(255, int(v * 1.12)) for v in lit), lit, (y0, y0 + 18), noise=0.1)
    m = k.union(front, top)
    # the folds of the layers along the front, rounded at the left end
    for i in range(1, layers):
        y = y0 + 14 + (y1 - y0 - 14) * i / layers
        icon.line([(x0 + 26, y), (x1 - 12, y + 2)], 5, (30, 18, 12, 120))
        icon.line([(x0 + 26, y + 5), (x1 - 12, y + 7)], 3, (255, 245, 225, 60))
    k.tint(icon, icon.mask("rectangle", (x0, y0, x0 + 40, y1)), m, (255, 250, 235), 0.22, blur=10)
    k.tint(icon, icon.mask("rectangle", (x1 - 40, y0, x1, y1)), m, (0, 0, 0), 0.3, blur=12)
    k.strokes(icon, m, (0, 0, 0), 24, 0, 7, 2, 0.4, (20, 60))
    k.contour(icon, m)
    return m


def charge(icon, k):
    _bolt(icon, k, 340, 560, 684, 668, (214, 200, 168))  # undyed wool, bottom
    _bolt(icon, k, 356, 448, 668, 566, (52, 74, 132))  # woad blue
    _bolt(icon, k, 376, 336, 648, 454, (170, 52, 40))  # madder red, top
    # binding cord over the stack
    k.rope(icon, [(590, 330), (596, 450), (600, 560), (604, 670)], 16, (198, 172, 120))
    # lead cloth seal hanging from the cord
    icon.line([(598, 470), (560, 520)], 5, (40, 34, 28, 255))
    k.ball(icon, 552, 532, 30, (142, 146, 152))
    icon.overlay(lambda d: d.ellipse((538, 518, 566, 546), outline=(50, 50, 56, 200), width=4))
