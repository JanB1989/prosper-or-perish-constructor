"""Liquor: a copper pot still (alembic) on a brick hearth, its swan neck running into a receiving flask, on a
teal field; a square case bottle and a long-necked flask stand on either side below the shield."""

FIELD = "#24585a"
SEED = 31


def _bottle(icon, sx, mirror, k):
    if not mirror:  # square case bottle (gin), shoulders and a short neck
        pts = [(70, 600), (230, 600), (240, 640), (240, 980), (60, 980), (60, 640)]
        neck = [(128, 520), (172, 520), (176, 604), (124, 604)]
        k.block(icon, [(sx(x), y) for x, y in neck], (170, 170, 170))
        m = k.block(icon, [(sx(x), y) for x, y in pts], (180, 180, 180), light=1.4)
        k.tint(icon, icon.mask("rectangle", (min(sx(80), sx(110)), 660, max(sx(80), sx(110)), 960)), m,
               (255, 255, 255), 0.35, blur=6)
        k.block(icon, [(sx(x), y) for x, y in [(118, 500), (182, 500), (182, 530), (118, 530)]], (120, 120, 120))
        k.tint(icon, icon.mask("rectangle", (0, 760, 1024, 860)), m, (0, 0, 0), 0.25)  # label band
    else:  # round flask with a long neck
        cx = 150
        body = k.ell(icon, sx(cx), 860, 110, 116)
        neck = icon.mask("rectangle", (min(sx(cx - 26), sx(cx + 26)), 560, max(sx(cx - 26), sx(cx + 26)), 760))
        m = k.union(body, neck)
        k.rfill(icon, m, (sx(cx) - 40, 820), 170, ((0, (240, 240, 240)), (0.5, (160, 160, 160)), (1, (70, 70, 70))))
        k.contour(icon, m)
        k.rod(icon, (sx(cx), 556), (sx(cx), 590), 64, (190, 190, 190))
        k.ball(icon, sx(cx), 540, 24, (140, 140, 140))


def props(icon, k):
    k.flank(icon, lambda ic, sx, mirror: _bottle(ic, sx, mirror, k))


def charge(icon, k):
    copper = ((0, (255, 200, 150)), (0.3, (214, 120, 64)), (0.7, (140, 64, 30)), (1, (70, 28, 12)))
    # brick hearth with a glowing fire mouth
    hearth = icon.mask("rectangle", (352, 640, 592, 760))
    icon.fill(hearth, (160, 84, 60), (100, 50, 36), (640, 760))
    for r, y in enumerate(range(640, 760, 24)):
        icon.line([(352, y), (592, y)], 4, (60, 34, 24, 200))
        for x in range(352 + (r % 2) * 24, 592, 48):
            icon.line([(x, y), (x, y + 24)], 4, (60, 34, 24, 200))
    mouth = k.union(icon.mask("ellipse", (430, 676, 514, 740)), icon.mask("rectangle", (430, 708, 514, 760)))
    k.rfill(icon, mouth, (472, 740), 70, ((0, (255, 230, 120)), (0.5, (240, 120, 30)), (1, (90, 20, 10))))
    k.contour(icon, k.union(hearth, mouth))
    # onion pot
    pot = k.ell(icon, 472, 552, 128, 108)
    k.rfill(icon, pot, (420, 500), 230, copper, noise=0.1)
    for y in (520, 600):  # riveted seams
        for x in range(372, 580, 26):
            if (x - 472) ** 2 / 128 ** 2 + (y - 552) ** 2 / 108 ** 2 < 0.9:
                icon.draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(90, 40, 18, 255))
    k.contour(icon, pot)
    # helmet (still head)
    helm = k.union(k.ell(icon, 472, 410, 70, 64), icon.mask("rectangle", (420, 420, 524, 460)))
    k.rfill(icon, helm, (446, 380), 130, copper, noise=0.1)
    k.contour(icon, helm)
    # swan neck to the receiver
    neck = k.bezier((520, 380), (600, 300), (660, 330), (662, 520), 30)
    nm = k.line_mask(icon, neck, 30)
    k.rfill(icon, nm, (600, 320), 240, copper, noise=0.08)
    k.contour(icon, nm)
    # receiving flask of green glass
    rx, ry = 650, 620
    flask = k.union(k.ell(icon, rx, ry, 56, 60), icon.mask("rectangle", (rx - 16, 520, rx + 16, 580)))
    k.rfill(icon, flask, (rx - 20, ry - 20), 90, ((0, (210, 240, 210)), (0.6, (90, 150, 110)), (1, (30, 70, 46))))
    k.tint(icon, k.Icon.intersect(flask, icon.mask("rectangle", (0, 630, 1024, 700))), flask, (200, 140, 60), 0.6)
    icon.overlay(lambda d: d.line([(rx - 30, ry - 30), (rx - 36, ry + 4)], fill=(255, 255, 255, 200), width=7))
    k.contour(icon, flask)
    k.tint(icon, k.ell(icon, 430, 510, 40, 30), pot, (255, 240, 220), 0.35, blur=10)
