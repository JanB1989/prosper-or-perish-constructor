"""Books: an open bound book with written pages and a ribbon marker on a gules field; crossed quill pens
behind the shield."""

FIELD = "#8e3328"
SEED = 32


def _quill(icon, loc, mirror, k):
    L = k.CROSS_LEN
    # bare shaft and cut nib at the butt
    k.rod(icon, *loc([(0, 40), (0, 560)]), 16, (200, 200, 200))
    nib = loc([(-9, 40), (9, 40), (0, -20)])
    k.block(icon, nib, (150, 150, 150))
    # vane: wide on one side, narrow on the other, ragged edge
    side_a = k.bezier((0, 520), (70, 640), (110, 900), (10, L + 10), 22)
    side_b = k.bezier((10, L + 10), (-40, 920), (-50, 700), (0, 560), 18)
    vane = loc(side_a + side_b[1:])
    m = icon.poly_mask(vane)
    a, b = loc([(-50, 800), (100, 800)])
    k.cyl(icon, m, a, b, 150, (200, 200, 200), spec=1.3)
    # barbs and a few splits
    for v in range(600, L - 40, 34):
        p, q = loc([(4, v), (80 - (v - 600) * 0.05, v + 60)])
        icon.line([p, q], 3, (70, 70, 70, 120))
        p, q = loc([(-2, v), (-36, v + 40)])
        icon.line([p, q], 3, (70, 70, 70, 100))
    k.rod(icon, *loc([(2, 560), (8, L - 20)]), 10, (240, 240, 240), edge=False)
    k.contour(icon, m)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _quill(ic, loc, mirror, k))


def charge(icon, k):
    cx = 512
    # cover (visible under and around the page block)
    cover = [(316, 352), (cx, 382), (708, 352), (720, 650), (cx, 690), (304, 650)]
    k.block(icon, cover, (120, 40, 34), light=1.2)
    # page block thickness
    for s in (-1, 1):
        block = [(cx, 372), (cx + s * 190, 340), (cx + s * 196, 628), (cx, 672)]
        icon.fill(icon.poly_mask(block), (226, 214, 186), (170, 152, 120), (340, 672))
        for i in range(5):
            icon.line([(cx + s * 196, 600 + i * 6), (cx, 650 + i * 4)], 2, (120, 100, 70, 150))
    # pages, curling up from the gutter
    for s in (-1, 1):
        edge_top = k.bezier((cx, 360), (cx + s * 60, 300), (cx + s * 150, 300), (cx + s * 196, 316), 16)
        edge_bot = k.bezier((cx + s * 190, 602), (cx + s * 140, 590), (cx + s * 60, 600), (cx, 650), 16)
        page = edge_top + edge_bot
        pm = icon.poly_mask(page)
        k.dfill(icon, pm, (cx, 0), (s, 0), 200, ((0, (180, 166, 136)), (0.25, (248, 240, 222)), (1, (232, 222, 198))),
                noise=0.06)
        # lines of writing, with a red initial
        for i in range(9):
            y = 340 + i * 28
            x_in = cx + s * 40
            x_out = cx + s * 170
            if i == 0:
                icon.draw.rectangle((min(x_in, x_in + s * 30), y - 4, max(x_in, x_in + s * 30), y + 26),
                                    fill=(170, 40, 30, 255))
                x_in += s * 40
            icon.overlay(lambda d, a=x_in, b=x_out, y=y: d.line([(a, y + 8), (b, y + 4)], fill=(60, 50, 40, 170),
                                                                 width=5), pm)
        k.contour(icon, pm, 5)
    # ribbon marker hanging down from the gutter
    rib = [(cx - 12, 640), (cx + 14, 640), (cx + 24, 760), (cx + 2, 740), (cx - 18, 768)]
    k.block(icon, rib, (40, 70, 150), light=1.5)
