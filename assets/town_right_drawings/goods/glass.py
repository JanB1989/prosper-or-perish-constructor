"""Glass: a blown green-glass goblet (Venetian, with knopped stem) on a purpure field; crossed glassblower's
pipes with blown bubbles behind the shield."""

FIELD = "#573066"
SEED = 26


def _pipe(icon, loc, mirror, k):
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 40), (0, L - 150)]), 26, (150, 150, 150))
    k.rod(icon, *loc([(0, 0), (0, 70)]), 40, (120, 120, 120))  # mouthpiece
    k.rod(icon, *loc([(0, 360), (0, 600)]), 40, (100, 100, 100))  # wooden grip
    # the gather blown into a bubble at the tip
    # the gather blown into a round bubble on a short neck
    k.rod(icon, *loc([(0, L - 230), (0, L - 150)]), 40, (170, 170, 170))
    c = loc([(0, L - 76)])[0]
    m = k.ell(icon, c[0], c[1], 74)
    k.rfill(icon, m, (c[0] - 30, c[1] - 30), 110, ((0, (255, 255, 255)), (0.25, (200, 200, 200)),
                                                  (0.75, (110, 110, 110)), (1, (210, 210, 210))), noise=0.05)
    icon.overlay(lambda d: d.arc((c[0] - 56, c[1] - 56, c[0] + 56, c[1] + 56), 30, 120, fill=(255, 255, 255, 200),
                                 width=8))
    k.contour(icon, m)

def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: _pipe(ic, loc, mirror, k))


def charge(icon, k):
    cx = 512
    glass = ((0, (214, 240, 214)), (0.4, (122, 184, 140)), (0.8, (52, 108, 74)), (1, (30, 70, 46)))
    # bowl: a wide funnel with a rounded base
    bowl_pts = k.bezier((cx - 150, 236), (cx - 150, 380), (cx - 90, 470), (cx, 476), 20)
    bowl_pts += [(2 * cx - x, y) for x, y in bowl_pts[::-1]]
    bowl = icon.poly_mask(bowl_pts)
    k.rfill(icon, bowl, (cx - 70, 300), 260, glass, noise=0.06)
    # wine-less glass: show the far rim and a liquid-like inner shadow
    k.tint(icon, icon.mask("ellipse", (cx - 150, 220, cx + 150, 262)), bowl, (240, 255, 240), 0.5)
    k.tint(icon, icon.mask("ellipse", (cx - 130, 230, cx + 130, 254)), bowl, (40, 80, 56), 0.4)
    k.fade(icon, bowl, 0.78)
    # highlights
    icon.overlay(lambda d: d.line(k.bezier((cx - 110, 270), (cx - 116, 360), (cx - 80, 430), (cx - 30, 452), 12),
                                  fill=(255, 255, 255, 210), width=14, joint="curve"))
    icon.overlay(lambda d: d.line([(cx + 98, 280), (cx + 92, 350)], fill=(255, 255, 255, 140), width=8))
    k.contour(icon, bowl, 6)
    icon.overlay(lambda d: d.ellipse((cx - 152, 222, cx + 152, 262), outline=(236, 255, 236, 230), width=6))
    # stem with knops and a lion-mask style hollow knop
    for y0, y1, w in ((476, 506, 46), (506, 540, 30), (540, 600, 74), (600, 634, 30), (634, 660, 50), (660, 690, 24)):
        m = icon.mask("ellipse", (cx - w / 2, y0, cx + w / 2, y1)) if w > 40 else \
            icon.mask("rectangle", (cx - w / 2, y0, cx + w / 2, y1))
        k.rfill(icon, m, (cx - w * 0.25, (y0 + y1) / 2 - 8), w * 0.9, glass, noise=0.05)
        k.contour(icon, m, 5)
    icon.overlay(lambda d: d.line([(cx - 12, 552), (cx - 18, 588)], fill=(255, 255, 255, 200), width=7))
    # foot
    foot = icon.mask("ellipse", (cx - 132, 676, cx + 132, 728))
    k.rfill(icon, foot, (cx - 60, 690), 180, glass, noise=0.05)
    k.fade(icon, foot, 0.85)
    icon.overlay(lambda d: d.arc((cx - 120, 682, cx + 120, 722), 200, 300, fill=(255, 255, 255, 180), width=6))
    k.contour(icon, foot, 6)
    # a few seeds (bubbles) in the glass
    for x, y, r in ((cx + 40, 330, 6), (cx - 30, 400, 5), (cx + 70, 410, 4)):
        icon.overlay(lambda d, x=x, y=y, r=r: d.ellipse((x - r, y - r, x + r, y + r), outline=(240, 255, 240, 200),
                                                         width=2))
