"""Tools: an anvil with a glowing bar on a tenne field; crossed sledgehammers behind the shield."""

FIELD = "#9a5a2e"
SEED = 13


def _sledge(icon, loc, mirror, k):
    L = k.CROSS_LEN
    p0, p1 = loc([(0, 0), (0, L - 80)])
    k.rod(icon, p0, p1, 40, (118, 118, 118))
    # wedge collar where the handle meets the head
    k.rod(icon, *loc([(0, L - 210), (0, L - 170)]), 52, (150, 150, 150))
    head = loc([(-128, L - 176), (118, L - 176), (134, L - 160), (134, L - 50), (118, L - 34), (-128, L - 34),
                (-144, L - 50), (-144, L - 160)])
    m = icon.poly_mask(head)
    a, b = loc([(0, L - 176), (0, L - 34)])
    k.cyl(icon, m, a, b, 160, (176, 176, 176), spec=1.5)
    for s in (-1, 1):  # struck faces at both ends
        f = loc([(s * 118, L - 170), (s * 140, L - 154), (s * 140, L - 56), (s * 118, L - 40)])
        k.tint(icon, icon.poly_mask(f), m, (255, 255, 255) if s < 0 else (0, 0, 0), 0.3)
    k.contour(icon, m)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _sledge(ic, loc, mirror, k))


def charge(icon, k):
    # anvil: horn to the left, flat face, narrow waist, spreading feet
    top, face = 430, 486
    body = [(334, top + 10), (440, top - 4), (686, top - 4), (698, top + 6), (698, face + 8), (636, face + 32),
            (606, face + 82), (600, 646), (660, 688), (680, 730), (376, 730), (396, 688), (456, 646), (450, face + 82),
            (420, face + 32), (392, face + 16), (338, top + 42), (318, top + 26)]
    m = icon.poly_mask(body)
    k.dfill(icon, m, (318, 400), (1, 0.6), 480,
            ((0, (126, 124, 128)), (0.35, (88, 86, 92)), (0.7, (52, 50, 56)), (1, (26, 25, 28))), noise=0.18)
    topf = icon.poly_mask([(334, top + 10), (440, top - 4), (686, top - 4), (698, top + 6), (698, top + 24),
                           (440, top + 22), (336, top + 28)])
    k.tint(icon, topf, m, (232, 228, 220), 0.6, blur=3)
    k.tint(icon, icon.poly_mask([(456, 570), (600, 570), (600, 646), (456, 646)]), m, (0, 0, 0), 0.35, blur=14)
    k.tint(icon, icon.poly_mask([(376, 708), (680, 708), (680, 730), (376, 730)]), m, (0, 0, 0), 0.3, blur=6)
    k.tint(icon, k.ell(icon, 392, top + 30, 50, 14), m, (255, 250, 240), 0.25, blur=6)
    k.contour(icon, m)
    # glowing bar on the face, with a warm glow on the iron around it
    k.tint(icon, k.ell(icon, 570, top + 10, 130, 40), m, (255, 150, 50), 0.35, blur=20)
    bar = icon.mask("rounded_rectangle", (482, top - 42, 650, top + 2), radius=14)
    k.dfill(icon, bar, (482, top - 42), (0.2, 1), 46,
            ((0, (255, 248, 210)), (0.4, (255, 200, 90)), (1, (200, 74, 22))), noise=0.08)
    k.contour(icon, bar, 5, (70, 24, 8, 220))
    icon.draw.rectangle((630, top + 6, 648, top + 16), fill=(24, 22, 24, 255))
