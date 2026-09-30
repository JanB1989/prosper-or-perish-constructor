"""Banjara Tanda (pp_banjara_tanda): camp of the Banjara pack-bullock carriers of India.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pp_banjara_tanda/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pp_banjara_tanda

Identity: a big pale canvas camp tent with red-and-saffron embroidered borders, a scalloped
valance and a pennant, a smaller tent behind, and two humped zebu pack bullocks with painted
horns, each under a mirror-worked saddle cloth and fat grain sacks; more sacks stacked by the
tent. Humped cattle, grain sacks and bright cloth keep it apart from the camel caravan icons.
Caravan-family helpers copied from pp_caravanserai (see there); ``zebu`` adapted from the cow in
cattle_farm; local: ``tent``, ``pack``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("caravan_stop", "caravanserai", "tambo", "market_village")

BASE = 890
GROUND = 944
CANVAS = ("#dcaa5c", "#8a5c28")
STRIPE = (150, 44, 26, 120)
RED = ("#c43a26", "#5a140a")
SAFFRON = (230, 164, 40)


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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.0, long: float = 1.0) -> None:
    """Coursed stone where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.85, 1.12)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.4, 2.4) * long
            j = lambda: rnd(-2, 2)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(70, 60, 44, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 50)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(40, 26, 14, shadow), width=5)
            x += w
        y += h
    paste_clipped(ic, lay, m)


def pointed(x0: float, x1: float, spring: float, bottom: float, k: float = 0.82, n: int = 18) -> list:
    """Two-centred pointed arch opening from ``bottom`` up to the springing line and the apex."""
    w = x1 - x0
    r = w * k
    mid = (x0 + x1) / 2
    th_mid = math.acos((mid - x0 - r) / r)
    left = [(x0 + r + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, th_mid, n)]
    right = [(x1 - (px - x0), py) for px, py in left[::-1]]
    return [(x0, bottom)] + left + right[1:] + [(x1, bottom)]


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.14, base - h * 0.8), (nx - w * 0.1, base - h * 1.02), (nx - w * 0.2, base - h * 1.12),
            (nx + w * 0.02, base - h * 1.08), (nx + w * 0.2, base - h * 1.14), (nx + w * 0.12, base - h * 1.0),
            (nx + w * 0.15, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.13, base - h * 0.96), (nx + w * 0.13, base - h * 0.95)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))


def rope(ic: Icon, pts, width: int = 6, color=(176, 146, 100)) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, color)


def road(ic: Icon, top: float, bot: float, c=("#c9a878", "#8e7048"), x0: float = 16, x1: float = 1008,
         ruts: bool = False) -> Image.Image:
    """Dusty ground band with pebbles, hoof marks and a shaded far edge; returns its mask."""
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def marks(d: ImageDraw.ImageDraw) -> None:
        if ruts:
            for y in (top + (bot - top) * 0.45, top + (bot - top) * 0.78):
                x = x0 + 10
                while x < x1 - 10:
                    ln = rnd(60, 160)
                    d.line([(x, y + rnd(-3, 3)), (x + ln, y + rnd(-3, 3))], fill=(50, 36, 20, 110), width=int(rnd(6, 9)))
                    x += ln + rnd(10, 50)
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


# ---------------------------------------------------------------- zebu (cow() from cattle_farm, adapted)
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def contour(ic: Icon, m: Image.Image, width: int = 7, alpha: float = 0.75, color=(30, 22, 16)) -> None:
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(int(width) // 2 * 2 + 1)))
    ic.shade(ring, color, alpha, blur=1)


COATS = {
    "zebu": (("#e0dace", "#6a645a"), None, None),
    "zebu_grey": (("#b4aea4", "#3e3a34"), None, None),
}


def zebu(ic: Icon, ox: float, oy: float, s: float = 1.0, left: bool = True, coat: str = "zebu", graze: bool = False,
        bull: bool = True, shadow: bool = True, legs: float = 1.0) -> Image.Image:
    """Humped zebu bullock (the cattle_farm cow with a hump over the withers, a pendulous dewlap,
    drooping ears and tall upswept painted horns). Standing in side view, hooves of the near fore leg at (ox, oy); ``s`` = scale (1 = ~570 px long).

    Head to the left unless ``left`` is False; ``graze`` lowers the head along the neck to the grass in
    front of the forefeet; ``bull`` gives a heavier crest, short thick horns and no udder; ``legs`` < 1
    shortens the legs (a stockier beast). Light stays upper left whichever way she faces.
    Returns the mask of the whole animal.
    """
    rnd = ic.random
    f = 1 if left else -1
    (c1, c2), face, patch = COATS[coat]

    def Y(y):  # legs below the belly line (-150) compressed by ``legs``, body lowered to match
        return y * legs if y > -150 else y + 150 * (1 - legs)

    def P(pts):
        return [(ox + f * x * s, oy + Y(y) * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def E(x0, y0, x1, y1):
        return ic.mask("ellipse", box(x0, y0, x1, y1))

    # head pose: poll position and rotation of the head's local points (poll = origin)
    poll, rot = ((-104, -172), -12) if graze else ((-70, -312), 0)
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    hs = 1.12

    def H(pts):
        return P([(poll[0] + (x * cr - y * sr) * hs, poll[1] + (x * sr + y * cr) * hs) for x, y in pts])

    if shadow:
        tint(ic, ic.mask("ellipse", box(-80, -26, 440, 22)), None, (10, 8, 4), 0.5, 12 * s)

    # ---- far legs and far horn, in shade (darker than the near legs so the body has depth)
    far_front = [(46, -210), (108, -210), (98, -140), (92, -102), (95, -86), (87, -52), (86, -20), (93, -8), (62, -8),
                 (65, -20), (64, -52), (58, -86), (60, -102), (52, -140)]
    far_hind = [(226, -214), (316, -236), (318, -180), (308, -136), (312, -110), (294, -90), (285, -56), (283, -20),
                (289, -8), (255, -8), (259, -20), (259, -56), (263, -92), (248, -122), (232, -152)]
    far = union(ic.poly_mask(P(far_front)), ic.poly_mask(P(far_hind)))
    ic.fill(far, tone(c1, 0.5), tone(c2, 0.45), (oy - 240 * s, oy), noise=0.2)
    tint(ic, ic.mask("rectangle", (0, oy - 36 * s, SIZE, oy)), far, (20, 16, 14), 0.8)
    contour(ic, far, 5, 0.6)
    horn_w = [30, 24, 16, 8]
    far_horn = [(8, 2), (26, -28), (36, -62), (30, -98)]
    hm, _, hb = tube(H(far_horn), horn_w)
    ic.fill(ic.poly_mask(hm), "#a8a08a", "#5a5446", noise=0.12)
    ic.outline(hm, 3, (40, 32, 24, 170))

    # ---- body mass: barrel, neck, dewlap and near legs filled as one form
    body = [(-24, -250), (6, -296), (60, -318), (160, -310), (262, -312), (332, -326), (374, -312), (394, -282),
            (398, -232), (384, -190), (344, -160), (262, -140), (150, -132), (60, -150), (10, -182)]
    neck = ([(70, -318), (20, -312), (-40, -306), (-84, -284), (-76, -216), (-36, -178), (20, -168), (40, -240)]
            if not graze else
            [(70, -318), (14, -306), (-50, -262), (-104, -196), (-118, -150), (-70, -130), (-24, -166), (20, -200)])
    if bull:
        neck = ([(100, -330), (40, -346), (-30, -332)] + neck[3:]) if not graze else \
            ([(100, -330), (30, -340), (-40, -292)] + neck[3:])
    dewlap = [(-70, -230), (-52, -150), (-20, -104), (20, -112), (40, -180)]
    hump = [(-10, -300), (4, -372), (40, -404), (86, -396), (116, -340), (120, -300)]
    # legs taper from forearm and gaskin to knee and hock; the hind leg bends back at the hock
    front = [(-10, -220), (72, -220), (62, -150), (56, -104), (59, -88), (50, -50), (50, -16), (57, 0), (19, 0),
             (24, -16), (24, -50), (17, -88), (20, -104), (8, -150)]
    hind = [(262, -230), (394, -250), (397, -190), (386, -142), (391, -114), (372, -94), (360, -60), (358, -18),
            (364, 0), (325, 0), (329, -18), (330, -60), (334, -96), (318, -124), (292, -150)]
    head = [(14, -8), (-24, -8), (-48, 14), (-70, 52), (-92, 92), (-108, 116), (-108, 140), (-82, 152), (-50, 144),
            (-20, 122), (4, 80), (22, 26)]
    legm = union(ic.poly_mask(P(front)), ic.poly_mask(P(hind)))
    mass = smooth(union(ic.poly_mask(P(body)), ic.poly_mask(P(neck)), ic.poly_mask(P(dewlap)), ic.poly_mask(P(hump)), legm,
                        E(250, -334, 398, -200), E(-20, -318, 120, -150), E(60, -250, 320, -122)), 10 * s)
    hmask = smooth(ic.poly_mask(H(head)), 5 * s)
    whole = union(mass, hmask)
    xs = [p[0] for p in P(body + head)]
    lx, top = min(xs), oy - 340 * s
    ic.fill(mass, c1, c2, radial=(lx + (max(xs) - lx) * 0.25, top, 600 * s), noise=0.2, chroma=0.08)

    # pied patches and white parts
    if patch:
        # a few irregular patches, each built from overlapping lobes; soft-edged, lit on the back, dark at the belly
        pm = blank()
        for lobes in (((30, -262, 70, 34, -14), (86, -236, 40, 30, 20)),
                      ((214, -278, 58, 30, 6), (262, -250, 34, 26, -30), (180, -300, 30, 16, 0)),
                      ((346, -236, 34, 50, -10),),
                      ((126, -190, 30, 18, 10), (100, -180, 16, 12, 0))):
            for cx, cy, rx, ry, rot in lobes:
                pts = ic.rotate(ic.jitter(0, 0, rx, ry, 11, 0.34), (0, 0), rot)
                pm = union(pm, ic.poly_mask(P([(cx + x, cy + y) for x, y in pts])))
        pm = smooth(pm, 7 * s).filter(ImageFilter.GaussianBlur(2.5 * s + 1))
        pm = ic.intersect(pm, mass)
        ic.fill(pm, tone(patch[0], 1.45), patch[1], (top + 10 * s, oy - 130 * s), noise=0.22, chroma=0.06)
        tint(ic, E(-20, -336, 400, -286), pm, (220, 214, 206), 0.16, 10 * s)
    if face:
        white = smooth(ic.poly_mask(P([(-70, -214), (-40, -150), (-6, -146), (6, -180), (-20, -214), (-50, -236)])),
                       8 * s).filter(ImageFilter.GaussianBlur(6 * s))
        ic.shade(ic.intersect(white, mass), face[1], 0.7)

    # volume: belly and brisket in shade (falling onto the upper legs), lit back, rump and shoulder forms
    tint(ic, E(-60, -210, 420, -90), mass, (16, 10, 6), 0.5, 18 * s)
    tint(ic, E(10, -340, 390, -280), mass, (255, 240, 214), 0.2, 16 * s)
    tint(ic, E(270, -330, 380, -250), mass, (255, 240, 214), 0.12, 12 * s)
    tint(ic, E(-30, -300, 70, -210), mass, (255, 240, 214), 0.1, 12 * s)
    tint(ic, ic.mask("rectangle", box(248, -310, 262, -180)), mass, (16, 10, 6), 0.2, 16 * s)
    tint(ic, ic.mask("rectangle", box(80, -300, 92, -180)), mass, (16, 10, 6), 0.14, 14 * s)
    if bull:
        tint(ic, E(-40, -350, 110, -280), mass, (255, 240, 214), 0.16, 14 * s)
    hair(ic, mass, box(-120, -340, 400, -40), int(600 * s * s), 10 * s, alpha=40)

    # legs: lit front edge, shadowed back edge, the stifle fold over the belly, dark hooves
    below = ic.mask("rectangle", (0, oy - 175 * s, SIZE, oy + 4))
    for leg in (front, hind):
        lm = ic.intersect(ic.poly_mask(P(leg)), mass)
        dr, dl = int(16 * s) + 1, int(10 * s) + 1  # screen-right edge in shade, screen-left edge lit
        right = ImageChops.subtract(lm, ImageChops.offset(lm, -dr, 0))
        leftb = ImageChops.subtract(lm, ImageChops.offset(lm, dl, 0))
        tint(ic, right, ic.intersect(lm, below), (10, 6, 2), 0.42, 5 * s)
        tint(ic, leftb, ic.intersect(lm, below), (255, 240, 214), 0.16, 3 * s)
        tint(ic, ic.mask("rectangle", (0, oy - 60 * legs * s, SIZE, oy)), lm, (16, 10, 6), 0.22, 10 * s)
        hoof = ic.intersect(lm, ic.mask("rectangle", (0, oy - 22 * legs * s, SIZE, oy + 4)))
        ic.fill(hoof, "#4a403a", "#161210", noise=0.1)
        ic.line(P([(12, -150), (24, -100)]) if leg is front else P([(292, -150), (318, -124), (331, -98)]),
                max(3, int(4 * s)), (30, 16, 8, 110))
    tint(ic, ic.poly_mask(P([(262, -220), (300, -228), (310, -140), (290, -146)])), mass, (16, 10, 6), 0.28, 10 * s)

    # tail down the rump
    tail, ta, _ = tube(P([(384, -306), (400, -250), (404, -180), (400, -112)]), [15 * s, 11 * s, 8 * s, 7 * s])
    ic.fill(ic.poly_mask(tail), tone(c1, 0.85), tone(c2, 0.8), noise=0.16)
    tint(ic, ic.poly_mask(tail), None, (10, 6, 2), 0.2)
    ic.outline(tail, 3, (40, 24, 14, 150))
    sw = ic.poly_mask(P(ic.jitter(400, -92, 14, 30, 9, 0.25)))
    ic.fill(sw, tone(c2, 1.1), tone(c2, 0.5), noise=0.3)
    hair(ic, sw, box(380, -130, 420, -60), 30, 16 * s, alpha=90)

    # udder tucked up between the hind legs, in the belly shadow: dusky flesh, no teats
    if not bull:
        um = smooth(E(242, -158, 284, -128), 3 * s)
        ic.fill(um, tone(c2, 1.25), tone(c2, 0.9), (oy - 160 * s, oy - 126 * s), noise=0.1)
        ic.shade(um.filter(ImageFilter.GaussianBlur(2 * s)), "#b88a78", 0.6)
        tint(ic, E(236, -172, 290, -142), um, (20, 10, 6), 0.45, 5 * s)
        tint(ic, E(250, -136, 292, -120), um, (20, 10, 6), 0.25, 4 * s)

    # ---- head
    hb = [p for p in H(head)]
    hrad = (min(p[0] for p in hb), min(p[1] for p in hb), 180 * s)
    cheek = smooth(ic.poly_mask(H([(20, 24), (8, 72), (-14, 104), (-40, 96), (-24, 50), (-4, 10)])), 5 * s)
    if face:
        # coat colour first, then the white face over it through a feathered mask: the white stays crisp
        # against the background but fades into the red neck and cheek
        ic.fill(hmask, c1, c2, radial=hrad, noise=0.16)
        outside = ImageChops.invert(mass)
        wm = ImageChops.subtract(union(hmask, outside), cheek).filter(ImageFilter.GaussianBlur(8 * s))
        wm = ic.intersect(wm, hmask.filter(ImageFilter.MaxFilter(int(6 * s) // 2 * 2 + 1)))
        ic.fill(wm, face[0], face[1], radial=hrad, noise=0.16)
    else:
        ic.fill(hmask, c1, c2, radial=hrad, noise=0.16)
        if patch:  # coloured cheek behind the eye, feathered
            ic.fill(ic.intersect(cheek.filter(ImageFilter.GaussianBlur(3 * s)), hmask), patch[0], patch[1], noise=0.18)
    hsh = (40, 26, 20)
    tint(ic, ic.poly_mask(H([(20, 24), (8, 72), (-12, 110), (-40, 132), (-60, 150), (20, 150)])), hmask, hsh,
         0.36, 8 * s)  # far cheek and jowl turned from the light
    tint(ic, ic.poly_mask(H([(-104, 128), (-84, 156), (-50, 150), (-18, 126), (6, 84), (-8, 80), (-34, 118),
                             (-76, 138)])), hmask, hsh, 0.34, 6 * s)  # lower jaw
    tint(ic, ic.poly_mask(H([(-22, -8), (-46, 12), (-68, 50), (-50, 60), (-28, 26)])), hmask, (255, 228, 184), 0.3,
         6 * s)  # warm light on the forehead
    muz = ic.intersect(hmask, ic.poly_mask(H(ic.jitter(-80, 124, 30, 24, 10, 0.05))))
    ic.fill(muz, "#c49a8c", "#6a4a42", noise=0.12)
    nx, ny = H([(-92, 122)])[0]
    ic.draw.ellipse((nx - 5 * s, ny - 4 * s, nx + 5 * s, ny + 4 * s), fill=(28, 16, 14, 255))
    ic.line(H([(-96, 138), (-72, 134)]), max(2, int(3 * s)), (40, 24, 20, 150))
    ex, ey = H([(-34, 42)])[0]
    ic.draw.ellipse((ex - 7 * s, ey - 5 * s, ex + 7 * s, ey + 5 * s), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 4 * s, ey - 3 * s, ex - 1 * s, ey), fill=(190, 180, 170, 255))
    ic.line(H([(-48, 34), (-32, 30), (-18, 36)]), max(2, int(3 * s)), (40, 24, 14, 120))
    # long ear hanging down beside the cheek, inner side pink in shadow
    ear = [(8, 16), (32, 16), (52, 40), (60, 70), (42, 70), (8, 36)]
    em = ic.poly_mask(H(ear))
    ic.fill(em, tone(c1 if not face else c1, 0.95), tone(c2, 0.9), noise=0.16)
    tint(ic, ic.poly_mask(H([(16, 24), (36, 24), (50, 50), (40, 60)])), em, (150, 90, 80), 0.45, 2)
    ic.outline(H(ear), 3, (40, 24, 14, 160))
    # forelock tuft and near horn
    ic.fill(ic.poly_mask(H(ic.jitter(-2, 4, 18, 12, 8, 0.25))), tone(c1 if not face else face[0], 0.9),
            tone(c2 if not face else face[1], 0.9), noise=0.2)
    near_horn = [(-6, 2), (-24, -30), (-30, -64), (-20, -100)]
    hm, ha, hb2 = tube(H(near_horn), horn_w)
    ic.fill(ic.poly_mask(hm), "#e2d8bc", "#8a8066", radial=(min(p[0] for p in hm), min(p[1] for p in hm), 60 * s),
            noise=0.1)
    tip = ic.intersect(ic.poly_mask(hm), ic.poly_mask(H(ic.jitter(*near_horn[-1], 14, 14, 8, 0.05))))
    ic.fill(ic.intersect(ic.poly_mask(hm), ic.poly_mask(H([(-60, -30), (20, -30), (20, -90), (-60, -90)]))),
            "#c43a2a", "#5a140c", noise=0.12)  # painted horn, brass tip
    ic.fill(tip, "#e0b850", "#6e5018", noise=0.1)
    ic.outline(hm, 3, (40, 32, 24, 180))
    if bull:
        rx, ry = H([(-96, 132)])[0]
        ic.overlay(lambda d: d.ellipse((rx - 12 * s, ry - 6 * s, rx + 12 * s, ry + 18 * s), outline=(150, 130, 70, 255),
                                       width=max(3, int(5 * s))))
    # head outline only where the head stands against the background, never across the neck
    ic.overlay(lambda d: d.line(hb + [hb[0]], fill=(40, 24, 14, 150), width=4, joint="curve"),
               ImageChops.invert(mass))
    ring = ImageChops.subtract(mass, mass.filter(ImageFilter.MinFilter(max(4, int(7 * s)) // 2 * 2 + 1)))
    ic.shade(ImageChops.subtract(ring, hmask), (30, 22, 16), 0.6, blur=1)
    return whole



# ---------------------------------------------------------------- camp
def border(ic: Icon, pts, width: float, clip: Image.Image | None = None) -> None:
    """Embroidered band along a polyline: red ground, saffron zigzag, small mirror dots."""
    ic.line(pts, int(width) + 8, (50, 16, 8))
    ic.line(pts, int(width), RED[0])
    zig = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / (width * 0.9)))
        for i in range(n):
            t = i / n
            off = width * 0.28 * (1 if i % 2 else -1)
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy) or 1
            zig.append((x0 + dx * t - dy / ln * off, y0 + dy * t + dx / ln * off))
    ic.line(zig, max(3, int(width * 0.2)), SAFFRON)
    for x, y in zig[::2]:
        ic.draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(236, 240, 236, 255))


def tent(ic: Icon, x0, x1, apex, eave, base, scale: float = 1.0, dim: float = 0.0) -> None:
    """Ridge tent seen end-on: canvas roof and walls, embroidered border, scalloped valance, open door."""
    cx = (x0 + x1) / 2
    w = x1 - x0
    roof = [(cx, apex), (x1 + w * 0.06, eave), (x0 - w * 0.06, eave)]
    walls = [(x0, eave), (x1, eave), (x1 + w * 0.02, base), (x0 - w * 0.02, base)]
    wm = ic.poly_mask(walls)
    ic.fill(wm, CANVAS[0], CANVAS[1], (eave, base), noise=0.14)
    sw = 34 * scale
    ic.overlay(lambda d: [d.line([(x, eave), (x + (x - cx) * 0.04, base)], fill=STRIPE, width=int(sw))
                          for x in np.arange(x0 + sw, x1, sw * 2.2)], wm)
    tint(ic, ic.mask("rectangle", (cx + w * 0.2, eave, x1 + 20, base)), wm, (40, 24, 8), 0.3, 20)
    for fx in (0.14, 0.36, 0.64, 0.86):  # canvas folds hanging from the eave
        x = x0 + w * fx
        tint(ic, ic.poly_mask([(x - 6, eave), (x + 6, eave), (x + 12, base), (x - 4, base)]), wm, (60, 40, 16), 0.2, 6)
    # the door: flaps tied back, dark inside with a glimpse of stacked sacks
    door = [(cx - w * 0.16, base), (cx - w * 0.06, eave + 10), (cx + w * 0.06, eave + 10), (cx + w * 0.16, base)]
    dm = ic.poly_mask(door)
    ic.fill(dm, "#3a2616", "#140a04", (eave, base), noise=0.1)
    with ic.clipped(dm):
        for sx in (cx - w * 0.07, cx + w * 0.05):
            ic.fill(ic.mask("ellipse", (sx - 30 * scale, base - 70 * scale, sx + 30 * scale, base + 10)), "#6a5438",
                    "#2e2214", noise=0.2)
    for sgn in (-1, 1):
        flap = [(cx + sgn * w * 0.06, eave + 10), (cx + sgn * w * 0.19, base - (base - eave) * 0.45),
                (cx + sgn * w * 0.2, base), (cx + sgn * w * 0.15, base)]
        ic.poly(flap, "#e2d2ae", "#8e7c5a", edge=4)
        ic.line([(cx + sgn * w * 0.12, eave + (base - eave) * 0.45), (cx + sgn * w * 0.2, eave + (base - eave) * 0.5)],
                5, RED[0])
    ic.outline(walls, 5)
    rm = ic.poly_mask(roof)
    ic.fill(rm, CANVAS[0], CANVAS[1], (apex, eave), noise=0.14)
    tint(ic, ic.poly_mask([(cx, apex), (x1 + w * 0.06, eave), (cx, eave)]), rm, (40, 24, 8), 0.28)
    tint(ic, ic.poly_mask([(cx, apex), (cx - w * 0.2, eave), (x0 - w * 0.06, eave)]), rm, (255, 246, 220), 0.2, 20)
    ic.outline(roof, 5)
    border(ic, [(x0 - w * 0.05, eave - 14 * scale), (cx, apex + 22 * scale), (x1 + w * 0.05, eave - 14 * scale)],
           26 * scale)
    # valance of alternating coloured scallops along the eave
    cols = [RED, ("#e8a632", "#7a4a0c"), ("#2e7a5a", "#0e3222"), RED, ("#3a5aa0", "#142250")]
    n = max(5, int(w / (46 * scale)))
    for i in range(n + 1):
        a = x0 - w * 0.06 + i * (w * 1.12) / (n + 1)
        b = a + (w * 1.12) / (n + 1)
        c = cols[i % len(cols)]
        sc = [(a, eave - 4), (b, eave - 4), (b - 4, eave + 22 * scale), ((a + b) / 2, eave + 40 * scale), (a + 4, eave + 22 * scale)]
        ic.poly(sc, c[0], c[1], edge=3)
        ic.draw.ellipse(((a + b) / 2 - 4, eave + 14 * scale, (a + b) / 2 + 4, eave + 22 * scale), fill=(236, 240, 236, 255))
    # pole finial and pennant
    ic.line([(cx, apex + 10), (cx, apex - 70 * scale)], max(6, int(12 * scale)), (80, 56, 32))
    pen = [(cx, apex - 70 * scale), (cx + 90 * scale, apex - 52 * scale), (cx, apex - 30 * scale)]
    ic.poly(pen, "#e87a24", "#8a3a08", edge=4)
    ic.draw.ellipse((cx - 8 * scale, apex - 80 * scale, cx + 8 * scale, apex - 64 * scale), fill=(214, 170, 60, 255))
    if dim:
        whole = union(wm, rm, ic.poly_mask(pen))
        tint(ic, whole.filter(ImageFilter.MaxFilter(21)), None, (40, 30, 20), dim)


def pack(ic: Icon, ox, oy, s, cloth=RED, sack_c=("#cfae78", "#6a5030"), left: bool = True) -> None:
    """Pack gear on a zebu (same local frame as ``zebu`` facing left): a mirror-worked saddle cloth
    with tassels, a big jute grain sack slung on the near flank and a second across the back."""

    def P(pts):
        return [(ox + (1 if left else -1) * x * s, oy + y * s) for x, y in pts]

    cl = P([(116, -338), (330, -330), (338, -196), (300, -184), (140, -186), (106, -200)])
    cm = ic.poly_mask(cl)
    ic.fill(cm, cloth[0], cloth[1], (oy - 338 * s, oy - 184 * s), noise=0.16)
    border(ic, P([(112, -206), (220, -198), (334, -206)]), 16 * s)
    ic.outline(cl, 4, (40, 14, 8, 200))
    for x in np.linspace(124, 324, 7):  # tassels
        px, py = P([(x, -192)])[0]
        ic.line([(px, py), (px + 2, py + 26 * s)], max(3, int(6 * s)), (230, 170, 50))
        ic.draw.ellipse((px - 6 * s, py + 22 * s, px + 8 * s, py + 36 * s), fill=(200, 50, 40, 255))
    # near flank sack, bulging, tied at the neck with twine
    neck = [(196, -350), (190, -392), (174, -410), (206, -400), (226, -414), (246, -402), (236, -390), (236, -350)]
    ic.fill(ic.poly_mask(P(neck)), sack_c[0], sack_c[1], noise=0.16)
    ic.outline(P(neck), 3, (50, 36, 20, 200))
    sk = [(176, -370), (262, -372), (298, -330), (320, -254), (310, -194), (250, -164), (176, -166), (128, -196),
          (120, -262), (140, -330)]
    sm = smooth(ic.poly_mask(P(sk)), 8 * s)
    bx = P(sk)
    ic.fill(sm, sack_c[0], sack_c[1], radial=(min(p[0] for p in bx), min(p[1] for p in bx), 240 * s), noise=0.2)
    sx0, sx1 = min(p[0] for p in bx), max(p[0] for p in bx)
    tint(ic, ic.mask("rectangle", (sx0 + (sx1 - sx0) * 0.65, 0, SIZE, SIZE)), sm, (30, 18, 6), 0.3, 14 * s)
    tint(ic, ic.mask("rectangle", (0, P([(0, -210)])[0][1], SIZE, SIZE)), sm, (30, 18, 6), 0.3, 12 * s)
    tint(ic, ic.mask("ellipse", (sx0 + 10, min(p[1] for p in bx) + 10, sx0 + (sx1 - sx0) * 0.5,
                                 min(p[1] for p in bx) + 90 * s)), sm, (255, 240, 200), 0.25, 10 * s)
    ic.overlay(lambda d: [d.line(P([(x, -364), (x + 4, -170)]), fill=(90, 66, 36, 40), width=3) for x in range(140, 312, 18)], sm)
    ic.overlay(lambda d: d.line(P([(120, -300), (318, -300)]), fill=(40, 60, 120, 220), width=max(4, int(10 * s))), sm)
    rim(ic, sm, 4, (50, 36, 20), 0.8)
    ic.line(P([(196, -356), (236, -356)]), 6, (110, 80, 44))
    rope(ic, P([(210, -160), (206, -140), (190, -120)]), 4, (150, 116, 70))  # girth


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.84
    ic.grade["gamma"] = 0.74
    tent(ic, 780, 990, 470, 640, BASE - 40, scale=0.7, dim=0.18)
    tent(ic, 70, 520, 190, 540, BASE)
    road(ic, BASE - 8, 978, c=("#c89c68", "#8a6038"))
    for cx, base, w, h, c in ((80, 936, 92, 96, ("#d2b27c", "#6e5230")), (160, 948, 96, 104, ("#c4a26c", "#624828"))):
        sack(ic, cx, base, w, h, c=c)
    tint(ic, ic.mask("ellipse", (330, GROUND - 24, 1000, GROUND + 22)), None, (0, 0, 0), 0.4, 14)
    zebu(ic, 930, GROUND - 22, 0.72, left=False, coat="zebu_grey")
    pack(ic, 930, GROUND - 22, 0.72, cloth=("#2e6a8a", "#0e2a3e"), sack_c=("#b89a6a", "#5a4428"), left=False)
    zebu(ic, 372, GROUND, 0.86, coat="zebu")
    pack(ic, 372, GROUND, 0.86)
