"""Cattle Farm (cattle_farm): common pasture with a red cow in front of a low thatched byre.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/cattle_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/cattle_farm

Identity (tier 0 of the cattle chain): a big white-faced red cow standing on the common grass, a
low wattle-and-daub byre with a straw roof and an open doorway behind her, a woven hurdle closing
the yard. Households graze cattle on common pasture and bring them in at night.

Local helpers (shared by the four cattle tiers): ``cow`` (side-view cattle in several coats,
grazing or standing, cow or bull), ``pasture``, ``post``, ``rail_fence``, ``hurdle``, ``muck``
(manure heap), ``hair``; ``thatch``/``daub`` from wheat_farm, ``planks``/``stones``/``shingles``/``hay``
from tavern, ``tube``/``smooth``/``contour`` from elephant_kraal.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb


# ---------------------------------------------------------------- helpers (shared by the four cattle tiers)
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*ms: Image.Image) -> Image.Image:
    out = ms[0]
    for m in ms[1:]:
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


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def contour(ic: Icon, m: Image.Image, width: int = 7, alpha: float = 0.75, color=(30, 22, 16)) -> None:
    """Soft dark line just inside the edge of ``m`` (separates a form from what is behind it)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(int(width) // 2 * 2 + 1)))
    ic.shade(ring, color, alpha, blur=1)


def tube(path, widths, n: int = 40):
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    L = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / L, dx / L
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


# ---------------------------------------------------------------- cattle
COATS = {
    # coat (lit, shadow), face/white parts or None, patches or None
    "red": (("#c26a36", "#4a1e0c"), ("#eee6d6", "#a89a86"), None),
    "brown": (("#94603a", "#321c0e"), None, None),
    "chestnut": (("#b8582a", "#3a1404"), None, None),
    "dun": (("#c29c62", "#523820"), None, None),
    "pied": (("#eee8dc", "#8e867a"), None, ("#34302c", "#121010")),
    "black": (("#5a5048", "#16120e"), None, None),
}


def cow(ic: Icon, ox: float, oy: float, s: float = 1.0, left: bool = True, coat: str = "red", graze: bool = False,
        bull: bool = False, shadow: bool = True, legs: float = 1.0) -> Image.Image:
    """Standing cow in side view, hooves of the near fore leg at (ox, oy); ``s`` = scale (1 = ~570 px long).

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
    horn_w = [30, 24, 16, 8] if bull else [20, 15, 10, 5]
    far_horn = [(8, 4), (30, -4), (46, -18), (50, -36)] if not bull else [(6, 4), (26, -4), (40, -12), (44, -24)]
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
    dewlap = [(-60, -214), (-24, -140), (24, -146), (30, -196)] if not graze else [(-80, -150), (-40, -120), (10, -150)]
    # legs taper from forearm and gaskin to knee and hock; the hind leg bends back at the hock
    front = [(-10, -220), (72, -220), (62, -150), (56, -104), (59, -88), (50, -50), (50, -16), (57, 0), (19, 0),
             (24, -16), (24, -50), (17, -88), (20, -104), (8, -150)]
    hind = [(262, -230), (394, -250), (397, -190), (386, -142), (391, -114), (372, -94), (360, -60), (358, -18),
            (364, 0), (325, 0), (329, -18), (330, -60), (334, -96), (318, -124), (292, -150)]
    head = [(14, -8), (-24, -8), (-48, 14), (-70, 52), (-92, 92), (-108, 116), (-108, 140), (-82, 152), (-50, 144),
            (-20, 122), (4, 80), (22, 26)]
    legm = union(ic.poly_mask(P(front)), ic.poly_mask(P(hind)))
    mass = smooth(union(ic.poly_mask(P(body)), ic.poly_mask(P(neck)), ic.poly_mask(P(dewlap)), legm,
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
    # ear sticking out sideways, inner side pink in shadow
    ear = [(8, 14), (38, 4), (66, 14), (62, 32), (30, 38), (6, 30)]
    em = ic.poly_mask(H(ear))
    ic.fill(em, tone(c1 if not face else c1, 0.95), tone(c2, 0.9), noise=0.16)
    tint(ic, ic.poly_mask(H([(16, 22), (40, 14), (60, 20), (34, 30)])), em, (150, 90, 80), 0.45, 2)
    ic.outline(H(ear), 3, (40, 24, 14, 160))
    # forelock tuft and near horn
    ic.fill(ic.poly_mask(H(ic.jitter(-2, 4, 18, 12, 8, 0.25))), tone(c1 if not face else face[0], 0.9),
            tone(c2 if not face else face[1], 0.9), noise=0.2)
    near_horn = [(-6, 4), (-30, 0), (-50, -14), (-56, -34)] if not bull else [(-4, 4), (-26, -2), (-42, -12), (-46, -24)]
    hm, ha, hb2 = tube(H(near_horn), horn_w)
    ic.fill(ic.poly_mask(hm), "#e2d8bc", "#8a8066", radial=(min(p[0] for p in hm), min(p[1] for p in hm), 60 * s),
            noise=0.1)
    tip = ic.intersect(ic.poly_mask(hm), ic.poly_mask(H(ic.jitter(*near_horn[-1], 14, 14, 8, 0.05))))
    ic.fill(tip, "#4a4238", "#201c18", noise=0.1)
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


# ---------------------------------------------------------------- ground, fences, yard
def pasture(ic: Icon, top_pts, bottom: float, colors=("#86903e", "#4c5420"), tufts: int = 30) -> Image.Image:
    """Grass ground band: uneven top edge, blotchy greens, grass strokes, tufts breaking the edge, earth lip."""
    rnd = ic.random
    pts = [tuple(p) for p in top_pts]
    poly = pts + [(pts[-1][0] - 10, bottom), (pts[0][0] + 10, bottom)]
    m = ic.poly_mask(poly)
    y0 = min(p[1] for p in pts)
    ic.fill(m, colors[0], colors[1], (y0, bottom), noise=0.3, chroma=0.14)
    x0, x1 = pts[0][0], pts[-1][0]
    for _ in range(40):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
        r = rnd.uniform(20, 60)
        col = rnd.choice([(255, 240, 180), (20, 30, 8), (150, 130, 60), (80, 110, 40)])
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y - r * 0.5, x + r * 1.6, y + r * 0.5)), m, col, rnd.uniform(0.08, 0.2),
             10)

    def grass(d):
        for _ in range(int((x1 - x0) * (bottom - y0) / 150)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
            L = rnd.uniform(10, 22) * (0.6 + 0.6 * (y - y0) / max(bottom - y0, 1))
            col = rnd.choice([(170, 176, 90, 110), (60, 80, 24, 130), (120, 140, 56, 110), (200, 190, 110, 80)])
            d.line([(x, y), (x + rnd.uniform(-8, 8), y - L)], fill=col, width=3)

    ic.overlay(grass, m)
    lip = [(p[0], p[1]) for p in [(x0 + 10, bottom - 24), (x1 - 10, bottom - 24), (x1 - 16, bottom + 4),
                                   (x0 + 16, bottom + 4)]]
    ic.fill(ic.poly_mask(lip), "#6a5030", "#3e2c18", noise=0.3)
    tint(ic, ic.mask("rectangle", (0, bottom - 60, SIZE, bottom - 20)), m, (20, 16, 6), 0.3, 12)

    def tuftpaint(d):
        for _ in range(tufts):
            i = rnd.randrange(len(pts) - 1)
            t = rnd.random()
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t + 6
            for _ in range(6):
                d.line([(x, y), (x + rnd.uniform(-10, 10), y - rnd.uniform(12, 26))],
                       fill=rnd.choice([(120, 140, 56, 255), (70, 90, 30, 255), (160, 164, 84, 255)]), width=4)
    ic.overlay(tuftpaint)
    return m


def yard(ic: Icon, top_pts, bottom: float, colors=("#806648", "#443220"), puddles=(),
         front_straw: float = 1.0) -> Image.Image:
    """Trodden farmyard: churned earth, wet dark and dry light blotches, scattered straw, hoof prints,
    puddles ``(cx, cy, rx)`` with a sky glint, grass tufts along the back edge, earth lip at the front.
    ``front_straw`` thins the straw in the front half of the yard."""
    rnd = ic.random
    pts = [tuple(p) for p in top_pts]
    poly = pts + [(pts[-1][0] - 10, bottom), (pts[0][0] + 10, bottom)]
    m = ic.poly_mask(poly)
    y0 = min(p[1] for p in pts)
    x0, x1 = pts[0][0], pts[-1][0]
    ic.fill(m, colors[0], colors[1], (y0, bottom), noise=0.34, chroma=0.12)
    for _ in range(50):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
        r = rnd.uniform(14, 44)
        col = rnd.choice([(255, 236, 190), (16, 10, 4), (16, 10, 4), (90, 96, 44)])
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y - r * 0.5, x + r * 1.6, y + r * 0.5)), m, col, rnd.uniform(0.1, 0.25), 6)

    def marks(d):
        for _ in range(int((x1 - x0) * (bottom - y0) / 500)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
            if front_straw < 1 and y > (y0 + bottom) / 2 and rnd.random() > front_straw:
                continue
            if rnd.random() < 0.85:
                a = rnd.uniform(0, math.pi)
                L = rnd.uniform(10, 26)
                d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)],
                       fill=rnd.choice([(214, 180, 104, 190), (170, 134, 70, 170), (236, 210, 140, 150)]), width=3)
            else:
                d.ellipse((x - 7, y - 4, x + 7, y + 4), fill=(20, 12, 6, 60))

    ic.overlay(marks, m)
    for cx, cy, rx in puddles:
        pm = ic.poly_mask(ic.jitter(cx, cy, rx, rx * 0.28, 12, 0.12))
        ic.fill(pm, "#8a9aa0", "#2e3a3c", (cy - rx * 0.3, cy + rx * 0.3), noise=0.1)
        ic.shade(ic.poly_mask(ic.jitter(cx - rx * 0.2, cy - rx * 0.06, rx * 0.5, rx * 0.06, 8, 0.1)), (230, 236, 236), 0.35)
        ic.outline(ic.jitter(cx, cy, rx, rx * 0.28, 12, 0.02), 3, (40, 30, 20, 120))
    lip = [(x0 + 10, bottom - 24), (x1 - 10, bottom - 24), (x1 - 16, bottom + 4), (x0 + 16, bottom + 4)]
    ic.fill(ic.poly_mask(lip), "#5e4428", "#34261a", noise=0.3)

    def tuftpaint(d):
        for _ in range(18):
            i = rnd.randrange(len(pts) - 1)
            t = rnd.random()
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t + 8
            for _ in range(6):
                d.line([(x, y), (x + rnd.uniform(-10, 10), y - rnd.uniform(10, 22))],
                       fill=rnd.choice([(120, 136, 56, 255), (70, 86, 30, 255), (150, 150, 80, 255)]), width=4)

    ic.overlay(tuftpaint)
    return m


def crown(ic: Icon, cx: float, cy: float, r: float, colors=("#6a7e3c", "#22301a"), trunk: bool = True) -> Image.Image:
    """Tree crown built from leaf clumps: lit clumps up left, dark gaps, no outlines; optional trunk."""
    rnd = ic.random
    if trunk:
        ic.poly([(cx - r * 0.1, cy + r * 1.25), (cx - r * 0.06, cy + r * 0.2), (cx + r * 0.08, cy + r * 0.2),
                 (cx + r * 0.14, cy + r * 1.25)], (104, 78, 52), (50, 34, 22), vertical=False, edge=4)
    blobs = [(cx + math.cos(a) * r * d, cy + math.sin(a) * r * d * 0.8, r * rnd.uniform(0.3, 0.46))
             for a, d in ((rnd.uniform(0, 2 * math.pi), rnd.uniform(0.2, 0.62)) for _ in range(16))]
    m = blank()
    for bx, by, br in blobs:
        m = union(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.85, 12, 0.14)))
    ic.fill(m, colors[0], colors[1], radial=(cx - r * 0.6, cy - r * 0.8, r * 2.2), noise=0.3, chroma=0.12)
    for bx, by, br in sorted(blobs, key=lambda b: b[1]):
        tint(ic, ic.mask("ellipse", (bx - br, by + br * 0.1, bx + br, by + br * 1.1)), m, (10, 16, 4), 0.35, 8)
        tint(ic, ic.mask("ellipse", (bx - br * 0.8, by - br * 0.8, bx + br * 0.3, by)), m, (230, 236, 170), 0.2, 8)

    def leaves(d):
        for _ in range(int(r * 2.2)):
            x, y = rnd.uniform(cx - r, cx + r), rnd.uniform(cy - r, cy + r)
            t = rnd.uniform(-1, 1)
            d.ellipse((x - 6, y - 4, x + 6, y + 4), fill=(220, 230, 150, int(t * 90)) if t > 0 else (10, 20, 4, int(-t * 110)))

    ic.overlay(leaves, m)
    contour(ic, m, 5, 0.5)
    return m


def post(ic: Icon, x: float, base: float, top: float, w: float = 26, wood=((138, 104, 70), (70, 48, 30))) -> None:
    """Split timber post with a weathered top."""
    rnd = ic.random
    pts = [(x - w / 2, base), (x - w / 2 + rnd.uniform(-2, 2), top + 6), (x - w * 0.1, top - rnd.uniform(0, 8)),
           (x + w / 2, top + rnd.uniform(0, 10)), (x + w / 2, base)]
    ic.fill(ic.poly_mask(pts), wood[0], wood[1], (x - w / 2, x + w / 2), vertical=False, noise=0.26)
    ic.line([(x - w * 0.15, top + 16), (x - w * 0.1, base - 10)], 2, (40, 26, 14, 100))
    ic.outline(pts, 4)


def rail_fence(ic: Icon, posts, h: float, rails=(0.3, 0.72), w: float = 24, rail_w: float = 16,
               wood=((150, 116, 80), (78, 54, 34))) -> None:
    """Post-and-rail fence through ``posts`` [(x, base), ...]; rails run between neighbouring posts."""
    rnd = ic.random
    for x, base in posts:
        post(ic, x, base, base - h, w, wood)
    for (xa, ba), (xb, bb) in zip(posts, posts[1:]):
        for fr in rails:
            ya, yb = ba - h * fr + rnd.uniform(-4, 4), bb - h * fr + rnd.uniform(-4, 4)
            ic.line([(xa, ya), (xb, yb)], int(rail_w + 6), (40, 28, 20, 220))
            ic.line([(xa, ya), (xb, yb)], int(rail_w), tone(wood[0], rnd.uniform(0.85, 1.0)))
            ic.line([(xa, ya - rail_w * 0.28), (xb, yb - rail_w * 0.28)], 3, (255, 236, 200, 70))
    for x, base in posts:  # post caps in front of the rails
        ic.line([(x - w * 0.3, base - h * 0.96), (x - w * 0.3, base - h * 0.02)], 3, (255, 236, 200, 50))


def hurdle(ic: Icon, x0: float, x1: float, base: float, h: float, lean: float = 0) -> Image.Image:
    """Woven wattle hurdle: upright stakes with hazel rods woven between them."""
    rnd = ic.random
    pts = [(x0, base), (x0 + lean, base - h), (x1 + lean, base - h + rnd.uniform(-6, 6)), (x1, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#8a6c48", "#4a3420", (base - h, base), noise=0.3, chroma=0.1)

    def weave(d):
        y = base - h + 6
        k = 0
        while y < base:
            for x in np.arange(x0 - 30, x1 + 30, 30):
                off = 15 if k % 2 else 0
                d.arc((x + off, y - 7, x + off + 34, y + 9), 190, 350, fill=(196, 160, 110, 120), width=4)
                d.arc((x + off, y - 5, x + off + 34, y + 11), 10, 170, fill=(40, 26, 12, 150), width=4)
            y += rnd.uniform(12, 16)
            k += 1

    ic.overlay(weave, m)
    for x in np.linspace(x0 + 10, x1 - 10, max(2, int((x1 - x0) / 60))):
        xx = x + rnd.uniform(-5, 5)
        ic.line([(xx, base + 4), (xx + lean, base - h - rnd.uniform(8, 20))], 12, (98, 72, 46))
        ic.line([(xx - 3, base), (xx - 3 + lean, base - h - 6)], 3, (190, 156, 110, 110))
    tint(ic, ic.mask("rectangle", (x0, base - h * 0.4, x1 + 40, base)), m, (20, 12, 4), 0.3, 12)
    ic.outline(pts, 4)
    return m


def muck(ic: Icon, x0: float, x1: float, base: float, top: float, steam: bool = True,
         wisps=((-0.2, 110, 0.3), (0.12, 140, 0.3))) -> Image.Image:
    """Manure heap: domed rotted mound with a lit straw crown, fresh bedding flecks, a wet dark foot and a
    contact shadow, steam ``wisps`` ``(offset from centre as share of width, height, opacity)``."""
    rnd = ic.random
    cx = (x0 + x1) / 2
    pts = [(x0 + (x1 - x0) * t + rnd.uniform(-5, 5),
            base - (base - top) * math.sin(math.pi * t) ** 0.5 + rnd.uniform(-6, 6)) for t in np.linspace(0, 1, 18)]
    tint(ic, ic.mask("ellipse", (x0 - 30, base - 26, x1 + 44, base + 26)), None, (10, 6, 2), 0.65, 10)
    m = ic.poly_mask(pts)
    ic.fill(m, "#5e4228", "#1c1208", radial=(x0 + (x1 - x0) * 0.3, top, (x1 - x0) * 0.8), noise=0.35, chroma=0.12)
    tint(ic, ic.mask("ellipse", (x0 + (x1 - x0) * 0.12, top - 20, x0 + (x1 - x0) * 0.62, top + (base - top) * 0.4)), m,
         (196, 156, 92), 0.4, 16)  # lit crown of fresh straw-brown bedding
    for _ in range(26):
        x, y = rnd.uniform(x0, x1), rnd.uniform(top, base)
        r = rnd.uniform(8, 22)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), m,
             rnd.choice([(12, 8, 4), (120, 90, 50), (60, 64, 30)]), 0.3, 3)

    def straw(d):
        for _ in range(int((x1 - x0) * 0.4)):
            x = rnd.uniform(x0, x1)
            yt = np.interp(x, [p[0] for p in pts], [p[1] for p in pts])
            y = rnd.uniform(yt, yt + (base - yt) * 0.55)
            a = rnd.uniform(0, math.pi)
            L = rnd.uniform(10, 24)
            col = rnd.choice([(214, 180, 104, 200), (170, 134, 70, 180), (236, 210, 140, 160)])
            d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (cx, top, x1 + 20, base)), m, (10, 6, 2), 0.3, 24)
    tint(ic, ic.mask("rectangle", (x0 - 10, base - 30, x1 + 10, base + 6)), m, (10, 6, 2), 0.45, 8)
    if steam:
        for k, (dx, h, alpha) in enumerate(wisps):
            sx = cx + (x1 - x0) * dx
            sy = np.interp(sx, [p[0] for p in pts], [p[1] for p in pts])
            path = [(sx + 16 * math.sin(t * 3.4 + k * 1.7), sy - h * t) for t in np.linspace(0, 1, 10)]
            outline_pts, _, _ = tube(path, [14, 26, 32, 30, 20, 8])
            wisp = ic.poly_mask(outline_pts).filter(ImageFilter.GaussianBlur(7))
            ic.shade(wisp, (246, 244, 238), alpha, clip=False)
    return m


def hay(ic: Icon, pts, strands: int = 220) -> Image.Image:
    """Loose hay: golden mass lit top-left, dark underside, many straw strokes, a few stray stalks."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#d0b068", "#6a5026", radial=(min(xs) + (max(xs) - min(xs)) * 0.3, min(ys), (max(ys) - min(ys)) * 1.4),
            noise=0.22)
    rnd = ic.random.uniform

    def straw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(strands):
            x, y = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
            a = rnd(-0.9, 0.9) + (math.pi if ic.random.random() < 0.5 else 0)
            ln = rnd(14, 40)
            t = rnd(-1, 1)
            col = (255, 240, 180, int(t * 110)) if t > 0 else (50, 34, 10, int(-t * 110))
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (min(xs), (min(ys) + max(ys)) / 2 + 10, max(xs), max(ys))), m, (30, 16, 4), 0.35, 16)
    for _ in range(10):  # stray stalks sticking out of the silhouette
        i = ic.random.randrange(len(pts))
        x, y = pts[i]
        if y > max(ys) - 20:
            continue
        a = rnd(-2.6, -0.5)
        ic.line([(x, y + 6), (x + math.cos(a) * rnd(14, 26), y + math.sin(a) * rnd(14, 26))], 3, (196, 164, 92))
    return m


# ---------------------------------------------------------------- building materials
def thatch(ic: Icon, ridge, eave, c=("#a88c58", "#5a4626")) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.22, 0.41, 0.6, 0.79, 1.0]
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 26
        low = []
        for j in range(n + 1):
            t = j / n
            p = rl + (rr - rl) * t + ((el + (er - el) * t) - (rl + (rr - rl) * t)) * min(f1, 1.0)
            low.append((p[0] + rnd.uniform(-4, 4), p[1] + (rnd.uniform(-3, 7) if f1 < 1 else 0)))
        up = [tuple(rl + (el - rl) * f0 + np.array([-40, -4])), tuple(rr + (er - rr) * f0 + np.array([40, -4]))]
        band = ic.intersect(ic.poly_mask(up + low[::-1]), m)
        y0 = (rl + (el - rl) * f0)[1]
        y1 = max(p[1] for p in low)
        if f1 < 1:
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tn = rnd.uniform(0.92, 1.06)
        ic.fill(band, tone(c[0], tn), tone(c[1], tn), (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(220):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 22, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 8, (150, 128, 84, 170))


def daub(ic: Icon, box, posts=()) -> None:
    """Wattle-and-daub wall: uneven ochre plaster, grime low down, rough posts."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, "#b89c6c", "#86704a", noise=0.3, edge=0)
    for _ in range(18):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(10, 26)
        light = rnd.random() < 0.5
        ic.shade(ic.mask("ellipse", (x - r * 1.5, y - r, x + r * 1.5, y + r)), (255, 240, 210) if light else (60, 40, 20),
                 0.14, blur=6)
    ic.shade(ic.mask("rectangle", (x0, y1 - 50, x1, y1)), (50, 44, 20), 0.35, blur=14)
    for x in posts:
        ic.rect((x - 11, y0, x + 11, y1), "#8e6644", "#4e3420", vertical=False, noise=0.25, edge=3)


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, w - 4)
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.8, 1.15)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.2, 2.5)
            j = lambda: rnd(-3, 3)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 55)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=5)
            x += w
        y += h
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone_l = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone_l), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys), 0
    while y < max(ys):
        off = (k % 2) * stagger / 2 + rnd(-6, 6)
        x = min(xs) - stagger + off
        while x < max(xs):
            w = stagger * rnd(0.85, 1.15)
            q = [(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + course), (x + 2, y + course)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(20, 10, 6, int(-t * 60)) if t < 0 else (255, 236, 210, int(t * 40)))
            td.line([(x + w - 2, y + 6), (x + w - 2, y + course - 2)], fill=(40, 22, 14, 90), width=3)
            x += w
        yl = y + course + rnd(-2, 2)
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone_l, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m



SEED = 11
REFS = ("sheep_farms", "farming_village", "fulani_cattle_rearing_pen", "free_village")


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.9
    ic.grade["gamma"] = 0.72

    # ---- byre: low, long, thatched down to head height; open doorway
    ic.shade(ic.mask("ellipse", (40, 640, 660, 740)), alpha=0.4, blur=16, clip=False)
    daub(ic, (96, 470, 590, 700), posts=(102, 290, 440, 584))
    dx0, dx1 = 150, 262
    ic.rect((dx0, 540, dx1, 700), "#221810", "#0a0604", noise=0.1, edge=0)
    tint(ic, ic.mask("rectangle", (dx0, 540, dx1, 590)), None, (0, 0, 0), 0.4, 10)
    ic.beam((dx0 - 12, 536), (dx1 + 12, 536), 18, (108, 78, 50))
    ic.window(350, 530, 396, 570)
    ic.shade(ic.mask("rectangle", (96, 470, 590, 530)), alpha=0.5, blur=12)
    ridge = [(200, 262), (340, 254), (480, 264)]
    eave = [(x, 486 + rnd.uniform(-6, 8)) for x in np.linspace(30, 660, 22)]
    thatch(ic, ridge, eave, c=("#b09460", "#5e4828"))
    ic.shade(ic.poly_mask([(420, 240), (690, 240), (690, 520), (460, 520)]), alpha=0.2, blur=40)

    # ---- pasture
    top = [(10, 716)] + [(x, 698 + rnd.uniform(-14, 14)) for x in np.linspace(60, 960, 22)] + [(1014, 716)]
    grass = pasture(ic, top, 944, colors=("#7c8640", "#465020"))
    ic.shade(ic.mask("ellipse", (40, 660, 660, 740)), alpha=0.3, blur=18)
    # worn, trodden patch where the cow stands: paler bare earth showing through, a few hoof marks
    worn = ic.poly_mask(ic.jitter(640, 914, 310, 38, 16, 0.12))
    tint(ic, worn, grass, (186, 158, 108), 0.55, 16)
    tint(ic, ic.poly_mask(ic.jitter(600, 922, 180, 16, 12, 0.2)), grass, (150, 120, 76), 0.3, 8)
    for _ in range(9):
        x, y = rnd.uniform(380, 900), rnd.uniform(896, 934)
        ic.shade(ic.mask("ellipse", (x - 9, y - 4, x + 9, y + 4)), (40, 28, 14), 0.35, blur=1)

    # ---- hurdles closing the yard behind the cow
    hurdle(ic, 640, 800, 736, 150)
    hurdle(ic, 800, 990, 744, 146, lean=4)

    # ---- tall tufts breaking the back edge of the pasture (in front of the byre and the hurdle foot)
    def clumps(d):
        for x in (46, 128, 296, 342, 590, 718, 876, 968):
            y = np.interp(x, [p[0] for p in top], [p[1] for p in top]) + 10
            for _ in range(12):
                a = rnd.uniform(-2.3, -0.85)
                L = rnd.uniform(24, 52)
                x0 = x + rnd.uniform(-16, 16)
                d.line([(x0, y), (x0 + math.cos(a) * L, y + math.sin(a) * L)],
                       fill=rnd.choice([(112, 126, 50, 255), (70, 86, 30, 255), (138, 140, 70, 255), (90, 104, 40, 255)]),
                       width=5)

    ic.overlay(clumps)

    # ---- the cow
    cow(ic, 430, 912, 1.08, left=True, coat="red")
