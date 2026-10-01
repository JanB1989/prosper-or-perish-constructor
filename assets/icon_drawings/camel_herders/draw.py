"""Camel Herders (camel_herders): a herding camp of the desert edge.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/camel_herders/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/camel_herders

Identity: a long, low black goat-hair tent (bayt al-sha'r) pitched on three poles, its open front showing
a woven red-and-white partition, rugs and a camel saddle; a flat-topped acacia behind; a plastered
watering trough in front, an unladen dromedary cow at the trough and her calf before the tent.
No building, no load: this is the herd itself, not the caravan (the caravan posts carry bales and salt).

Helpers copied from the caravan family (pp_caravanserai): ``union``, ``tone``, ``tint``, ``paste_clipped``,
``rim``, ``smooth``, ``tube``, ``hair``, ``modelled``, ``rope``, ``road``, ``camel`` (here with
``load="none"``); new: ``goat_tent``, ``acacia``, ``trough``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 61
REFS = ("caravan_stop", "horse_breeders", "sheep_farms", "trans_saharan_trade_outposts")

BASE = 890  # foot of the tent
GROUND = 944  # where the camels stand
HAIR = ("#6c5a4a", "#261c14")  # goat-hair cloth


# ---------------------------------------------------------------- caravan-family helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tone(c, f: float) -> tuple[int, int, int]:
    return tuple(int(min(255, max(0, v * f))) for v in rgb(c))


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def rim(ic: Icon, m: Image.Image, width: int = 4, color=(40, 24, 12), alpha: float = 0.75) -> None:
    """Soft dark edge just inside a mask (a form's contour without a hard outline)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(2 * width + 1)))
    ic.shade(ring, color, alpha, blur=1)


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def tube(path, widths, n: int = 40):
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    ln = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / ln, dx / ln
    a = [(x + nx_ * w / 2, y + ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    b = [(x - nx_ * w / 2, y - ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    return a + b[::-1], a, b


def hair(ic: Icon, mask: Image.Image, box, n: int, length: float = 14, light=(255, 236, 206), dark=(30, 16, 8),
         alpha: int = 60) -> None:
    """Short coat strokes (hair lying back and down) clipped to ``mask``."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            t = rnd.uniform(-1, 1)
            col = light + (int(t * alpha),) if t > 0 else dark + (int(-t * alpha),)
            d.line([(x, y), (x + rnd.uniform(-4, 4), y + length * rnd.uniform(0.6, 1.2))], fill=col, width=3)

    ic.overlay(paint, mask)


def modelled(ic: Icon, m: Image.Image, s: float, light=(255, 222, 170), lit: float = 0.4, dark: float = 0.5) -> None:
    """Round an animal's flat mask: warm light along every upper-left edge, dark underside."""
    edge = ImageChops.subtract(m, ImageChops.offset(m, int(12 * s) + 1, int(26 * s) + 1))
    tint(ic, edge, m, light, lit, 7 * s)
    under = ImageChops.subtract(m, ImageChops.offset(m, -int(6 * s), -int(30 * s) - 1))
    tint(ic, under, m, (12, 6, 2), dark, 10 * s)


def rope(ic: Icon, pts, width: int = 6, color=(176, 146, 100)) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, color)


def road(ic: Icon, top: float, bot: float, c=("#c9a878", "#8e7048"), x0: float = 16, x1: float = 1008) -> Image.Image:
    """Dusty ground band with pebbles, hoof marks and a shaded far edge; returns its mask."""
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def marks(d: ImageDraw.ImageDraw) -> None:
        for _ in range(70):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 8, bot - 8)
            r = rnd(3, 8)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(236, 220, 186, 130))
            d.line([(x - r, y + r * 0.6), (x + r, y + r * 0.6)], fill=(50, 36, 20, 110), width=2)
        for _ in range(26):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 10, bot - 10)
            d.arc((x - 9, y - 5, x + 9, y + 5), 0, 180, fill=(60, 44, 24, 100), width=3)

    ic.overlay(marks, m)
    tint(ic, ic.mask("rectangle", (0, top, SIZE, top + 24)), m, (0, 0, 0), 0.32, 10)
    ic.outline(pts, 5)
    return m


# ---------------------------------------------------------------- dromedary
def camel(ic: Icon, X: float, G: float, s: float = 0.6, left: bool = True, load: str = "none",
          coat=("#cfa66c", "#5a3c20"), lead: bool = True) -> Image.Image:
    """Dromedary in profile standing on ``G``; head to the left unless ``left`` is False. ``load``:
    "none" (halter only). Local units, y up; returns the animal mask."""
    f = 1 if left else -1

    def P(pts):
        return [(X + f * x * s, G - y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def shift(pts, dx, dy=0):
        return [(x + dx, y + dy) for x, y in pts]

    for hx in (68, 118, 300, 346):  # hoof contact shadows
        cx = X + f * hx * s
        tint(ic, ic.mask("ellipse", (cx - 40 * s, G - 10 * s, cx + 40 * s, G + 14 * s)), None, (10, 6, 2), 0.55, 5)

    near_fore = [(22, 352), (104, 340), (94, 280), (84, 210), (90, 184), (80, 158), (74, 50), (86, 18), (100, 0),
                 (38, 0), (46, 18), (50, 50), (48, 158), (38, 184), (44, 210), (34, 280)]
    near_hind = [(276, 368), (386, 368), (392, 300), (376, 236), (362, 196), (368, 168), (358, 148), (352, 50),
                 (362, 18), (376, 0), (316, 0), (322, 18), (328, 50), (328, 148), (318, 176), (302, 236), (288, 300)]
    far = union(ic.poly_mask(P(shift(near_fore, 52))), ic.poly_mask(P(shift(near_hind, -48))))
    ic.fill(far, tone(coat[0], 0.55), tone(coat[1], 0.5), (G - 360 * s, G), noise=0.16)
    tint(ic, ic.mask("rectangle", (0, G - 30 * s, SIZE, G + 4)), far, (20, 14, 8), 0.6)
    rim(ic, far, 3, (20, 12, 6), 0.6)

    tl, _, _ = tube(P([(390, 430), (404, 370), (408, 310), (404, 262)]), [20 * s, 15 * s, 11 * s, 10 * s])
    ic.fill(ic.poly_mask(tl), tone(coat[0], 0.8), tone(coat[1], 0.8), noise=0.18)
    ic.fill(ic.poly_mask(P(ic.jitter(404, 250, 12, 26, 9, 0.25))), "#4a3220", "#1e140a", noise=0.2)

    body = [(10, 340), (-6, 392), (6, 444), (52, 470), (110, 480), (160, 522), (206, 558), (252, 542), (300, 484),
            (348, 462), (388, 430), (398, 384), (384, 340), (330, 310), (210, 300), (100, 306), (40, 318)]
    nk, _, _ = tube(P([(60, 420), (0, 382), (-60, 362), (-112, 382), (-146, 440), (-156, 518)]),
                    [150 * s, 100 * s, 78 * s, 68 * s, 64 * s, 60 * s])
    head = [(-126, 560), (-148, 592), (-196, 594), (-238, 578), (-272, 556), (-292, 530), (-288, 506), (-262, 494),
            (-226, 498), (-190, 506), (-156, 508), (-134, 520)]
    legs = union(ic.poly_mask(P(near_fore)), ic.poly_mask(P(near_hind)))
    mass = smooth(union(ic.poly_mask(P(body)), ic.poly_mask(nk), legs, ic.mask("ellipse", box(-10, 300, 130, 470)),
                        ic.mask("ellipse", box(250, 330, 400, 470))), 8 * s)
    hm = smooth(ic.poly_mask(P(head)), 5 * s)
    whole = union(mass, hm)
    xs = [p[0] for p in P(body + head)]
    ic.fill(whole, coat[0], coat[1], radial=(min(xs) + 80 * s, G - 640 * s, 760 * s), noise=0.18, chroma=0.06)
    modelled(ic, whole, s, (255, 226, 176), 0.42, 0.5)
    tint(ic, ic.mask("ellipse", box(0, 250, 400, 360)), whole, (16, 10, 4), 0.35, 16 * s)
    tint(ic, ic.mask("ellipse", box(130, 470, 280, 570)), whole, (255, 236, 200), 0.22, 14 * s)  # the lit hump
    tint(ic, ic.mask("rectangle", (0, G - 170 * s, SIZE, G)), legs, (30, 18, 8), 0.25, 10 * s)
    for leg in (near_fore, near_hind):
        lm = ic.intersect(ic.poly_mask(P(leg)), whole)
        tint(ic, ImageChops.subtract(lm, ImageChops.offset(lm, -int(12 * s) * f, 0)),
             ic.intersect(lm, ic.mask("rectangle", (0, G - 300 * s, SIZE, G))), (10, 6, 2), 0.4, 4 * s)
    for kx, ky in ((64, 172), (344, 158)):  # knee callosities
        ic.fill(ic.intersect(ic.mask("ellipse", box(kx - 22, ky - 16, kx + 22, ky + 16)), whole), "#6e5438", "#3a2814",
                noise=0.2)
    ic.fill(ic.intersect(whole, ic.mask("rectangle", (0, G - 18 * s, SIZE, G + 2))), "#5a4430", "#2a1e12", noise=0.12)
    hair(ic, whole, box(-290, 280, 400, 600), int(700 * s * s), 10 * s, alpha=34)
    # head: long face, heavy brow, drooping lip, small ear, halter
    tint(ic, ic.poly_mask(P([(-190, 506), (-262, 494), (-290, 510), (-270, 530), (-200, 520)])), hm, (20, 10, 4), 0.35,
         5 * s)
    tint(ic, ic.poly_mask(P([(-140, 590), (-200, 596), (-240, 578), (-200, 570), (-150, 572)])), hm, (255, 230, 186),
         0.3, 5 * s)
    ear = P([(-132, 582), (-122, 614), (-108, 610), (-112, 580)])
    ic.poly(ear, tone(coat[0], 0.9), tone(coat[1], 0.9), edge=3)
    ex, ey = P([(-176, 566)])[0]
    ic.draw.ellipse((ex - 6 * s / 0.7, ey - 4 * s / 0.7, ex + 6 * s / 0.7, ey + 4 * s / 0.7), fill=(18, 12, 10, 255))
    ic.line(P([(-192, 576), (-178, 576), (-164, 570)]), 3, (40, 26, 14, 170))
    nx, ny = P([(-278, 530)])[0]
    ic.line([(nx - 4, ny - 2), (nx + 6 * f, ny + 2)], 4, (30, 18, 10, 220))
    ic.line(P([(-286, 506), (-262, 500)]), 3, (40, 24, 12, 180))
    if lead:
        ic.line(P([(-160, 510), (-150, 560), (-140, 586)]), max(3, int(8 * s)), (70, 40, 24))  # halter
        ic.line(P([(-262, 520), (-158, 540)]), max(3, int(8 * s)), (70, 40, 24))
        ic.line(P([(-220, 508), (-232, 470), (-240, 420)]), max(3, int(7 * s)), (60, 40, 24))
    rim(ic, whole, 4, (40, 22, 8), 0.6)
    return whole


# ---------------------------------------------------------------- camp
def goat_tent(ic: Icon, x0: float, x1: float, poles, top: float, eave: float, base: float) -> Image.Image:
    """Black goat-hair tent seen from the open front: a long roof of woven strips peaked over the poles
    and sagging between them, side walls pegged out, a dark inside with a woven partition, rugs and a saddle."""
    rnd = ic.random.uniform
    w = x1 - x0
    # the inside: back wall of the tent, partly in deep shade
    inner = [(x0 + 4, eave + 10), (x1 - 4, eave + 10), (x1 - 14, base), (x0 + 14, base)]
    im = ic.poly_mask(inner)
    ic.fill(im, "#3e3024", "#140e08", (eave, base), noise=0.16)
    ic.overlay(lambda d: [d.line([(x0, y), (x1, y + rnd(-4, 4))], fill=(120, 96, 70, 60), width=4)
                          for y in np.arange(eave + 30, base, 26)], im)
    # the partition (sahah): a woven curtain with red, white and black bands, hung from the left pole
    px0, px1 = x0 + w * 0.08, x0 + w * 0.36
    part = [(px0, eave + 14), (px1, eave + 14), (px1 + 4, base - 4), (px0 - 4, base - 4)]
    pm = ic.poly_mask(part)
    ic.fill(pm, "#e2d4b8", "#8e7a5c", (eave, base), noise=0.14)
    bands = [(0.12, (150, 36, 24, 230), 22), (0.3, (30, 20, 14, 220), 12), (0.46, (150, 36, 24, 230), 26),
             (0.66, (30, 20, 14, 220), 12), (0.82, (150, 36, 24, 230), 22)]

    def weave(d):
        for fy, col, bw in bands:
            y = eave + 14 + (base - eave - 18) * fy
            d.line([(px0 - 4, y), (px1 + 4, y)], fill=col, width=bw)
            # small lozenges along the red bands
            if col[0] > 100:
                for x in np.arange(px0 + 14, px1, 30):
                    d.polygon([(x, y - bw * 0.35), (x + 9, y), (x, y + bw * 0.35), (x - 9, y)],
                              fill=(236, 220, 180, 220))
        for x in np.arange(px0, px1, 7):  # warp threads
            d.line([(x, eave + 14), (x + 1, base)], fill=(60, 40, 24, 30), width=2)

    ic.overlay(weave, pm)
    tint(ic, ic.mask("rectangle", (px0, eave, px1, eave + 60)), pm, (20, 10, 4), 0.45, 14)
    tint(ic, ic.mask("rectangle", (px1 - 50, eave, px1 + 20, base)), pm, (20, 10, 4), 0.3, 14)
    ic.outline(part, 3, (40, 24, 12, 180))
    # rugs and a camel saddle on the floor of the men's side
    rug = [(x0 + w * 0.4, base - 34), (x1 - 40, base - 40), (x1 - 20, base + 2), (x0 + w * 0.38, base + 2)]
    rm_ = ic.poly_mask(rug)
    ic.fill(rm_, "#a8402a", "#4e160c", (base - 40, base), noise=0.2)
    ic.overlay(lambda d: [d.line([(x0 + w * 0.4, y), (x1 - 30, y)], fill=(226, 190, 110, 170), width=5)
                          for y in (base - 24, base - 10)], rm_)
    sx = x0 + w * 0.62
    saddle = [(sx - 50, base - 36), (sx - 40, base - 96), (sx - 24, base - 70), (sx + 24, base - 70), (sx + 40, base - 98),
              (sx + 52, base - 36)]
    ic.poly(saddle, "#8a6440", "#3e2814", edge=4)
    ic.fill(ic.mask("rounded_rectangle", (sx - 44, base - 72, sx + 44, base - 40), radius=10), "#c84a30", "#5a1a0e",
            noise=0.16)
    for k in range(4):  # cushions / grain sacks against the back wall
        cx = x1 - 70 - k * 54
        sk = ic.mask("rounded_rectangle", (cx - 30, base - 104, cx + 30, base - 38), radius=18)
        ic.fill(sk, "#bfa478" if k % 2 else "#a8865a", "#4e3a22", radial=(cx - 20, base - 100, 90), noise=0.2)
        rim(ic, sk, 3, (30, 18, 8), 0.6)
    tint(ic, ic.mask("rectangle", (x0, eave, x1, eave + 90)), im, (0, 0, 0), 0.55, 24)  # roof shade inside

    # side walls pegged out at both ends
    for sgn, xe in ((-1, x0), (1, x1)):
        side = [(xe - sgn * 6, eave + 6), (xe + sgn * 46, eave + 24), (xe + sgn * 64, base + 4), (xe - sgn * 10, base + 4)]
        sm = ic.poly_mask(side)
        ic.fill(sm, HAIR[0], HAIR[1], (eave, base), noise=0.22)
        ic.overlay(lambda d, xe=xe, sgn=sgn: [d.line([(xe - 20, y), (xe + sgn * 70, y + 6)], fill=(150, 126, 100, 70),
                                                     width=4) for y in np.arange(eave + 30, base, 28)], sm)
        if sgn > 0:
            tint(ic, sm, sm, (0, 0, 0), 0.25)
        ic.outline(side, 4)
    # front poles
    for px in poles:
        ic.line([(px, base + 2), (px + rnd(-3, 3), eave - 6)], 16, (60, 40, 22))
        ic.line([(px - 2, base + 2), (px - 2, eave - 6)], 10, (150, 112, 70))
        ic.line([(px - 4, base), (px - 4, eave)], 3, (210, 180, 130, 110))
    # the roof: peaks over the poles, sags between them, woven strips running along the tent
    top_pts = [(x0 - 40, eave + 26)]
    front = []
    for i, px in enumerate(poles):
        top_pts.append((px, top + rnd(-6, 6)))
        front.append((px, eave - 12))
        if i + 1 < len(poles):
            mid = (px + poles[i + 1]) / 2
            for t, dy in ((0.25, 26), (0.5, 38), (0.75, 26)):  # the cloth sags in a curve between the poles
                top_pts.append((px + (poles[i + 1] - px) * t, top + dy + rnd(-4, 4)))
            front.append((mid, eave + 12))
    top_pts.append((x1 + 40, eave + 26))
    roof = top_pts + [(x1 + 40, eave + 26)] + front[::-1] + [(x0 - 40, eave + 26)]
    roof_m = smooth(ic.poly_mask(roof), 8)
    ic.fill(roof_m, HAIR[0], HAIR[1], (top, eave + 30), noise=0.24, chroma=0.06)

    def strips(d):
        y = top - 20
        k = 0
        while y < eave + 30:
            d.line([(x0 - 60, y), (x1 + 60, y + rnd(-5, 5))], fill=(150, 124, 96, 70) if k % 2 else (10, 6, 2, 80),
                   width=int(rnd(16, 24)))
            y += rnd(28, 36)
            k += 1
        for _ in range(500):  # coarse weave flecks
            x, yy = rnd(x0 - 40, x1 + 40), rnd(top - 10, eave + 30)
            d.line([(x, yy), (x + rnd(6, 14), yy + rnd(-1, 1))], fill=(190, 166, 130, 60), width=2)

    ic.overlay(strips, roof_m)
    # light from the upper left on the slopes towards each peak, shade on the far side
    for i, px in enumerate(poles):
        tint(ic, ic.poly_mask([(px - 120, eave), (px, top - 10), (px, eave)]), roof_m, (255, 232, 196), 0.18, 20)
        tint(ic, ic.poly_mask([(px, top - 10), (px + 140, eave), (px, eave)]), roof_m, (0, 0, 0), 0.25, 20)
    tint(ic, ic.mask("rectangle", (x0 - 50, eave - 30, x1 + 50, eave + 30)), roof_m, (0, 0, 0), 0.3, 12)
    ic.outline(roof, 5)
    # guy ropes out to the pegs
    for sx_, sy_, ex_, ey_ in ((x0 - 30, eave + 22, x0 - 100, base + 30), (x1 + 30, eave + 22, x1 + 100, base + 30)):
        rope(ic, [(sx_, sy_), (ex_, ey_)], 4, (190, 166, 120))
        ic.line([(ex_ - 6, ey_ - 18), (ex_ + 4, ey_ + 6)], 10, (110, 80, 50))
    return union(roof_m, im)


def acacia(ic: Icon, foot, crown, rx: float, ry: float) -> None:
    """Flat-topped desert acacia: a forked grey trunk and a wide, thin umbrella crown."""
    (fx, fy), (cx, cy) = foot, crown
    kx, ky = fx + 6, fy - 300  # where the trunk forks
    for path, w in (([(kx, ky), (kx - 40, ky - 120), (cx - rx * 0.62, cy + 20)], [20, 14, 8]),
                    ([(kx, ky), (kx + 4, ky - 140), (cx - rx * 0.05, cy + 12)], [18, 13, 8]),
                    ([(kx, ky), (kx + 50, ky - 110), (cx + rx * 0.55, cy + 18)], [20, 14, 8]),
                    ([(fx, fy), (fx - 12, fy - 170), (kx, ky - 10)], [36, 28, 22])):
        tr, _, _ = tube(path, w)
        ic.fill(ic.poly_mask(tr), "#8a7a64", "#3a2e22", (cx - rx, cx + rx), vertical=False, noise=0.2)
        ic.outline(tr, 3, (40, 28, 16, 180))
    m = Image.new("L", (SIZE, SIZE), 0)
    rnd = ic.random.uniform
    for _ in range(14):
        bx, by = cx + rnd(-rx * 0.85, rx * 0.85), cy + rnd(-ry * 0.4, ry * 0.3)
        br = rnd(rx * 0.18, rx * 0.3)
        m = union(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.38, 12, 0.16)))
    ic.fill(m, "#8a9244", "#2e3614", radial=(cx - rx * 0.6, cy - ry, rx * 1.6), noise=0.3, chroma=0.1)
    tint(ic, ic.mask("rectangle", (cx - rx - 20, cy + 4, cx + rx + 20, cy + ry + 30)), m, (10, 14, 2), 0.45, 10)

    def leaves(d):
        for _ in range(int(rx * 1.6)):
            x, y = rnd(cx - rx, cx + rx), rnd(cy - ry, cy + ry)
            t = rnd(-1, 1)
            d.ellipse((x - 5, y - 3, x + 5, y + 3), fill=(220, 226, 150, int(t * 90)) if t > 0 else (10, 18, 4, int(-t * 100)))

    ic.overlay(leaves, m)
    rim(ic, m, 3, (20, 26, 8), 0.6)


def trough(ic: Icon, x0: float, x1: float, top: float, bot: float) -> None:
    """Mud-plastered stone watering trough with dark water and a lit rim."""
    face = ic.mask("rounded_rectangle", (x0, top + 18, x1, bot), radius=10)
    ic.fill(face, "#b89062", "#6a4a2a", (top, bot), noise=0.26)
    for _ in range(10):
        x, y = ic.random.uniform(x0, x1), ic.random.uniform(top + 20, bot)
        tint(ic, ic.mask("ellipse", (x - 16, y - 8, x + 16, y + 8)), face, (60, 30, 10), 0.18, 4)
    tint(ic, ic.mask("rectangle", (x1 - 40, top, x1 + 10, bot)), face, (30, 14, 4), 0.35, 10)
    rimm = ic.mask("rounded_rectangle", (x0 - 6, top, x1 + 6, top + 30), radius=12)
    ic.fill(rimm, "#d8b682", "#8e6a40", (top, top + 30), noise=0.18)
    water = ic.mask("rounded_rectangle", (x0 + 10, top + 6, x1 - 10, top + 22), radius=6)
    ic.fill(water, "#6a8486", "#22383a", (top, top + 22), noise=0.1)
    ic.overlay(lambda d: d.line([(x0 + 20, top + 10), (x0 + (x1 - x0) * 0.5, top + 10)], fill=(220, 236, 230, 120),
                                width=3), water)
    ic.outline([(x0 - 6, top + 8), (x1 + 6, top + 8), (x1, bot), (x0, bot)], 4)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    ic.grade["gamma"] = 0.66
    acacia(ic, (840, 900), (800, 336), 196, 56)
    goat_tent(ic, 70, 600, (118, 335, 552), 400, 600, BASE)
    road(ic, BASE - 8, 978, c=("#e0ba82", "#a07848"), x0=24, x1=1000)
    tint(ic, ic.mask("ellipse", (470, GROUND - 26, 1000, GROUND + 26)), None, (0, 0, 0), 0.4, 14)
    trough(ic, 420, 590, 862, 950)
    camel(ic, 712, GROUND, 0.7, coat=("#b47e46", "#3a200c"))
    camel(ic, 240, GROUND + 18, 0.44, left=False, coat=("#d6aa72", "#5a3818"), lead=False)
