"""Clay Washmill (clay_washmill): a horse-driven round wash pit with stepped settling tanks.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/clay_washmill/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/clay_washmill

Identity: the round brick-lined wash pit full of red clay slurry, the gin post in its centre with one
thick sweep arm running from the post collar over the rim to the collar of a bay draught horse
walking round in front of the pit (the pugging slot); harrow tines hang from the arm into the
slurry and leave a wake. Behind on the right, two stepped brick settling tanks: red-brown water in
the upper one, clear grey-green water in the lower one, joined by a spout (levigation ponds). The
wash house stands behind the pit on the left; a heap of sticky dug clay with spade-cut faces lies
front left. Vanilla clay_pit (treadwheel crane over a heap) is the tier before; this one reads
through the horse, the round pit and the tanks. Local helpers: ``union``, ``tint``,
``paste_clipped``, ``timber``, ``bricks`` (copied from victualling_yard), new ``limb``, ``leg``,
``horse``, ``cylinder``, ``tank``, ``clay_heap``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("clay_pit", "pottery_workshop", "horse_breeders", "irrigation_systems")

BRICK, BRICK_DK = "#9c5a44", "#5a3024"
COPING, COPING_DK = "#bf947a", "#86604c"
SLURRY, SLURRY_DK = "#b8663e", "#6a3020"
WOOD, WOOD_DK = "#8a6240", "#4c3422"
LEATHER, LEATHER_DK = "#6a4028", "#2a1408"

# wash pit (1024 canvas): rim ellipse centre, radii, wall height
PX, PY, PRX, PRY, PH = 372, 500, 330, 122, 104
GROUND = 900  # where the horse and the heap stand
HX, HS = 600, 1.46  # horse chest front x and scale


# ---------------------------------------------------------------- helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


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


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> Image.Image:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def bricks(ic: Icon, m: Image.Image, box, base=BRICK, dark=BRICK_DK, course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:  # over-burnt header
                col = (40, 22, 18, 90)
            else:
                col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    paste_clipped(ic, lay, m)


def smooth(pts, n: int = 2):
    """Chaikin corner cutting on a closed polygon (soft animal contours)."""
    pts = [tuple(p) for p in pts]
    for _ in range(n):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out += [(p[0] * 0.75 + q[0] * 0.25, p[1] * 0.75 + q[1] * 0.25), (p[0] * 0.25 + q[0] * 0.75, p[1] * 0.25 + q[1] * 0.75)]
        pts = out
    return pts


def limb(ic: Icon, pts, widths, c1, c2, edge=None, side_shade: float = 0.3) -> Image.Image:
    """Tapered limb along a polyline (widths per point), lit left, shaded right; returns the mask.
    No hard rim unless ``edge`` is given."""
    pts = [np.array(p, float) for p in pts]
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        d = b - a
        n = np.array([-d[1], d[0]]) / (np.hypot(*d) or 1)
        left.append(tuple(p + n * widths[i] / 2))
        right.append(tuple(p - n * widths[i] / 2))
    poly = left + right[::-1]
    m = ic.poly_mask(poly)
    for p, w in zip(pts, widths):  # round joints
        m = union(m, ic.mask("ellipse", (p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2)))
    ys = [p[1] for p in poly]
    ic.fill(m, c1, c2, (min(ys) + (max(ys) - min(ys)) * 0.2, max(ys)), noise=0.12)
    # lit left edge, shadowed right edge: per segment strips so it follows the limb
    for i in range(len(pts) - 1):
        p, q = pts[i], pts[i + 1]
        w = max(widths[i], widths[i + 1])
        tint(ic, ic.poly_mask([tuple(p + [w * 0.1, 0]), tuple(q + [w * 0.1, 0]), tuple(q + [w, 0]), tuple(p + [w, 0])]),
             m, (10, 4, 2), side_shade, 3)
        tint(ic, ic.poly_mask([tuple(p - [w * 0.5, 0]), tuple(q - [w * 0.5, 0]), tuple(q - [w * 0.2, 0]), tuple(p - [w * 0.2, 0])]),
             m, (255, 226, 190), 0.14, 3)
    if edge:
        ic.outline(poly, 3, edge)
    return m


def leg(ic: Icon, P, s: float, upper, knee, fetlock, hoof, wt: float, coat, dark: bool) -> None:
    """Horse leg: muscled upper part in the coat, bony knee/hock, slim dark cannon, feathered
    fetlock over a dark hoof. ``upper`` is a list of points from the body down to the joint."""
    c1, c2 = coat
    if upper:
        limb(ic, P(upper + [knee]), [w * s for w in wt[: len(upper)]] + [wt[-3] * s], c1, c2, side_shade=0.34)
        kx, ky = P([knee])[0]
        kw = wt[-3] * s * 1.15
        ic.fill(ic.mask("ellipse", (kx - kw / 2, ky - kw * 0.6, kx + kw / 2, ky + kw * 0.6)), c1, c2, (ky - kw, ky + kw),
                noise=0.1)
    pts_dark = ("#3a2418", "#120a06") if not dark else ("#22160e", "#0a0604")
    limb(ic, P([knee, fetlock]), [wt[-2] * s, wt[-1] * s], *pts_dark, side_shade=0.25)
    # feathering: pale hair flaring over the hoof
    fx, fy = P([fetlock])[0]
    hx, hy = P([hoof])[0]
    fw = wt[-1] * s
    hoof_poly = [(hx - fw * 0.75, hy - fw * 0.5), (hx + fw * 0.6, hy - fw * 0.5), (hx + fw * 0.85, hy + 2), (hx - fw * 1.0, hy + 2)]
    ic.poly(hoof_poly, "#2a221c", "#0c0806", noise=0.1, edge=0)
    feather = [(fx - fw * 0.4, fy - fw * 1.1), (fx + fw * 0.45, fy - fw * 1.1), (hx + fw * 0.95, hy - fw * 0.25),
               (hx + fw * 0.2, hy - fw * 0.05), (hx - fw * 0.5, hy - fw * 0.2), (hx - fw * 1.05, hy - fw * 0.3)]
    fc = ("#e2d6c0", "#9a8a74") if not dark else ("#9a8c78", "#4a4034")
    fm = ic.poly_mask(smooth(feather, 1))
    ic.fill(fm, fc[0], fc[1], (fy - fw, hy), noise=0.2)
    R = ic.random

    def hair(d: ImageDraw.ImageDraw) -> None:
        for _ in range(9):
            x = R.uniform(fx - fw * 0.4, fx + fw * 0.4)
            d.line([(x, fy - fw * 0.8), (x + (x - fx) * 1.4 + R.uniform(-4, 6), hy - fw * 0.1)],
                   fill=(40, 30, 22, 90) if R.random() < 0.5 else (255, 250, 236, 110), width=2)

    ic.overlay(hair, fm)
    tint(ic, ic.mask("rectangle", (fx + fw * 0.1, fy - fw * 1.2, hx + fw * 1.2, hy)), fm, (30, 20, 12), 0.35, 4)


def horse(ic: Icon, x0: float, gy: float, s: float) -> Image.Image:
    """Bay draught horse walking left and leaning into the collar, head lowered: deep barrel chest,
    arched neck, heavy head, black mane and tail, knees and hocks, feathered legs; padded collar with
    hames in dark leather. (x0, gy) = chest front at the ground line. Returns the coat mask."""
    def P(pts):
        return [(x0 + u * s, gy + v * s) for u, v in pts]

    def E(a, b):
        (ax, ay), (bx, by) = P([a, b])
        return ic.mask("ellipse", (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)))

    far = ("#562a14", "#1c0c04")
    # far legs (in shadow): fore planted, hind stepping forward
    leg(ic, P, s, [(40, -120), (40, -90)], (40, -62), (42, -20), (43, -2), [38, 28, 21, 15, 14], far, True)
    leg(ic, P, s, [(168, -150), (178, -104)], (186, -66), (176, -20), (172, -2), [60, 38, 21, 15, 14], far, True)
    # tail
    tail = P(smooth([(226, -196), (242, -188), (254, -160), (258, -124), (254, -92), (246, -72), (236, -80),
                     (238, -116), (234, -150), (226, -176)], 2))
    tm = ic.poly_mask(tail)
    ic.fill(tm, "#3a2a20", "#0e0806", (gy - 190 * s, gy - 74 * s), noise=0.25)
    ic.overlay(lambda d: [d.line(P([(238 + k * 4, -176), (248 + k * 3, -130), (244 + k * 2, -90)]), fill=(150, 116, 84, 90),
                                 width=3, joint="curve") for k in range(3)], tm)

    # coat mass: barrel body with the near forearm and gaskin, arched neck, heavy lowered head
    body = P(smooth([(-4, -186), (-18, -162), (-16, -136), (-6, -116), (-6, -90), (-8, -66), (6, -58), (12, -88),
                     (18, -106), (36, -98), (88, -86), (140, -94), (170, -108), (186, -122), (196, -100), (206, -72),
                     (208, -60), (224, -58), (228, -80), (238, -114), (244, -150), (242, -178), (230, -198), (200, -208),
                     (164, -200), (124, -192), (86, -198), (60, -218), (30, -208)], 2))
    neck = P(smooth([(64, -214), (36, -238), (4, -244), (-26, -234), (-46, -218), (-50, -190), (-34, -168),
                     (-14, -158), (10, -150), (40, -160)], 2))
    head = P(smooth([(-40, -224), (-64, -216), (-88, -186), (-104, -156), (-112, -138), (-106, -120), (-90, -116),
                     (-78, -128), (-62, -138), (-40, -150), (-28, -170), (-28, -200)], 2))
    bm = union(ic.poly_mask(body), ic.poly_mask(neck), ic.poly_mask(head))
    ic.fill(bm, "#b44c1c", "#300c02", (gy - 250 * s, gy - 70 * s), noise=0.12, chroma=0.06)
    # hindquarters turn away from the light
    tint(ic, E((150, -240), (270, -50)), bm, (20, 8, 2), 0.2, 30 * s)
    # barrel core shadow low along the belly, reflected light at the very bottom
    tint(ic, E((10, -150), (215, -86)), bm, (20, 8, 2), 0.4, 14 * s)
    tint(ic, E((40, -104), (160, -88)), bm, (190, 120, 80), 0.14, 5 * s)
    # lit masses: shoulder, chest front (three-quarter), croup, crest, forehead
    tint(ic, E((4, -214), (70, -126)), bm, (255, 190, 128), 0.3, 10 * s)
    tint(ic, E((-22, -184), (6, -120)), bm, (255, 198, 136), 0.26, 5 * s)
    tint(ic, E((140, -212), (228, -150)), bm, (255, 190, 128), 0.2, 10 * s)
    tint(ic, E((-30, -250), (50, -200)), bm, (255, 190, 128), 0.2, 8 * s)
    tint(ic, E((-72, -222), (-42, -170)), bm, (255, 198, 140), 0.24, 5 * s)
    # soft muscle separation (no lines): behind the shoulder, stifle crease, under the jaw
    tint(ic, E((64, -196), (92, -112)), bm, (30, 12, 4), 0.22, 8 * s)
    tint(ic, E((170, -170), (196, -110)), bm, (30, 12, 4), 0.2, 8 * s)
    tint(ic, E((-60, -160), (-26, -136)), bm, (24, 10, 4), 0.35, 5 * s)
    # forearm and gaskin darker toward the knee and hock
    tint(ic, E((-20, -90), (20, -50)), bm, (26, 12, 4), 0.35, 5 * s)
    tint(ic, E((196, -94), (234, -50)), bm, (26, 12, 4), 0.35, 5 * s)
    # dark muzzle
    tint(ic, E((-118, -160), (-84, -112)), bm, (26, 16, 12), 0.75, 4 * s)
    ic.outline(body, 2, (50, 24, 10, 80))
    ic.outline(head, 2, (50, 24, 10, 80))
    # blaze down the face
    blaze = P(smooth([(-58, -222), (-50, -216), (-72, -190), (-96, -156), (-106, -134), (-100, -152), (-80, -186)], 1))
    ic.fill(ic.poly_mask(blaze), "#ece2d0", "#a89a86", noise=0.08)
    # black mane falling on the near side of the crest, forelock
    crest = [(-40, -228), (-18, -240), (10, -250), (36, -244), (56, -228), (68, -214)]
    lower = [(x - 2 + ic.random.uniform(-3, 3), y + 18 + ic.random.uniform(-3, 6)) for x, y in crest[::-1]]
    mane = P(smooth(crest + [(72, -206)] + lower, 1))
    mm = ic.poly_mask(mane)
    ic.fill(mm, "#3c2c22", "#0c0806", noise=0.25)

    def strands(d: ImageDraw.ImageDraw) -> None:
        for (xa, ya), (xb, yb) in zip(crest[:-1], crest[1:]):
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            d.line(P([(mx, my + 2), (mx - 2, my + 16)]), fill=(150, 116, 84, 110), width=3)

    ic.overlay(strands, mm)
    ic.poly(P([(-46, -222), (-34, -226), (-50, -200), (-56, -206)]), "#3c2c22", "#100a06", edge=0)  # forelock
    for ear in (P([(-44, -222), (-54, -246), (-34, -228)]), P([(-34, -226), (-36, -250), (-24, -230)])):
        ic.poly(ear, "#8a4c28", "#2a140a", edge=2)
    ex, ey = P([(-66, -198)])[0]
    ic.draw.ellipse((ex - 6 * s, ey - 4 * s, ex + 6 * s, ey + 4 * s), fill=(16, 10, 8, 255))
    ic.draw.ellipse((ex - 4 * s, ey - 3 * s, ex - 1 * s, ey - 1 * s), fill=(170, 150, 130, 255))
    nx, ny = P([(-106, -130)])[0]
    ic.draw.ellipse((nx - 4 * s, ny - 4 * s, nx + 4 * s, ny + 4 * s), fill=(10, 6, 4, 255))

    # near lower legs: fore stepping forward from the knee, hind planted below the hock
    near = ("#8e4a24", "#3c1a08")
    leg(ic, P, s, None, (0, -64), (-10, -20), (-16, -2), [0, 0, 22, 16, 15], near, False)
    leg(ic, P, s, None, (216, -64), (212, -20), (210, -2), [0, 0, 22, 16, 15], near, False)

    # harness in dark leather (no black lines): padded collar hugging the neck base, lighter hames
    limb(ic, P([(40, -246), (36, -228), (24, -204), (8, -182), (-6, -168), (-14, -160)]),
         [14 * s, 20 * s, 24 * s, 26 * s, 22 * s, 14 * s], "#54321c", "#1c0c04", side_shade=0.25)
    ic.line(P([(32, -250), (28, -228), (16, -204), (0, -180), (-10, -168)]), 4, (168, 128, 70, 220))  # hames
    ic.line(P([(32, -252), (28, -230), (16, -206)]), 2, (240, 206, 150, 130))
    band = P([(104, -198), (106, -150), (102, -96)])  # back band and belly band
    ic.line(band, 9, (70, 44, 26))
    ic.line([(x - 3, y) for x, y in band[:2]], 3, (150, 110, 70, 140))
    ic.line(P([(94, -202), (116, -202)]), 12, (80, 52, 30))  # pad over the back
    return bm


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: every tile has its own tone, every course has a lit lower lip
    and casts a soft shadow onto the course below; courses waver slightly. Returns the roof mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
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
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def cylinder(ic: Icon) -> tuple[Image.Image, int]:
    """Round brick-lined wash pit seen from the raised camera: outer wall, coping ring, inner wall,
    red slurry. Returns the mask of the slurry and the slurry's inner radius y."""
    x0, x1 = PX - PRX, PX + PRX
    top = ic.mask("ellipse", (x0, PY - PRY, x1, PY + PRY))
    bot = ic.mask("ellipse", (x0, PY + PH - PRY, x1, PY + PH + PRY))
    wall = union(ic.mask("rectangle", (x0, PY, x1, PY + PH)), bot)
    bricks(ic, wall, (x0, PY - 10, x1, PY + PH + PRY), course=18, length=38)
    # roundness: lit left third, dark right edge, dark foot
    tint(ic, ic.mask("ellipse", (x0 + 30, PY - 40, x0 + PRX * 1.1, PY + PH + PRY)), wall, (255, 226, 190), 0.16, 30)
    tint(ic, ic.mask("rectangle", (x1 - 150, PY - 40, x1 + 20, PY + PH + PRY + 20)), wall, (20, 8, 4), 0.42, 40)
    tint(ic, ic.mask("rectangle", (x0 - 20, PY - 40, x0 + 50, PY + PH + PRY + 20)), wall, (20, 8, 4), 0.25, 24)
    tint(ic, ic.mask("ellipse", (x0 - 20, PY + PH - PRY + 40, x1 + 20, PY + PH + PRY + 30)), wall, (30, 26, 14), 0.3, 18)
    # coping ring
    ic.fill(top, COPING, COPING_DK, (PY - PRY, PY + PRY), noise=0.2)
    ic.overlay(lambda d: d.ellipse((x0, PY - PRY, x1, PY + PRY), outline=(50, 30, 20, 190), width=5))
    for a in np.linspace(0, 2 * math.pi, 26, endpoint=False):  # coping joints
        ca, sa = math.cos(a), math.sin(a)
        ic.line([(PX + ca * (PRX - 30), PY + sa * (PRY - 12)), (PX + ca * PRX, PY + sa * PRY)], 3, (60, 38, 26, 120))
    tint(ic, ic.mask("ellipse", (x0 - 10, PY - PRY - 10, PX + 60, PY + 20)), top, (255, 240, 214), 0.2, 20)
    # inside: dark inner wall (far side visible), slurry lower down
    ix0, ix1, iry = x0 + 30, x1 - 30, PRY - 12
    inner = ic.mask("ellipse", (ix0, PY - iry, ix1, PY + iry))
    bricks(ic, inner, (ix0, PY - iry, ix1, PY + iry), base="#6e3a2c", dark="#3a1c14", course=14, length=30)
    slurry = ic.intersect(inner, ic.mask("ellipse", (ix0 + 4, PY - iry + 34, ix1 - 4, PY + iry + 40)))
    ic.fill(slurry, SLURRY, SLURRY_DK, (PY - iry + 34, PY + iry), noise=0.12, chroma=0.06)
    tint(ic, ic.mask("rectangle", (ix0, PY - iry, ix1, PY - iry + 70)), slurry, (40, 16, 8), 0.4, 12)  # wall shadow
    rnd = ic.random.uniform

    def swirl(d: ImageDraw.ImageDraw) -> None:  # stirred slurry: concentric arcs, pale scum
        for _ in range(34):
            r = rnd(0.35, 0.95)
            cy = PY + 18
            box = (PX - (PRX - 40) * r, cy - (iry - 10) * r * 0.8, PX + (PRX - 40) * r, cy + (iry - 10) * r * 0.8)
            a0 = rnd(0, 360)
            d.arc(box, a0, a0 + rnd(20, 60), fill=(236, 190, 160, int(rnd(60, 120))), width=4)
            a0 = rnd(0, 360)
            d.arc(box, a0, a0 + rnd(20, 50), fill=(50, 20, 12, int(rnd(60, 110))), width=4)

    ic.overlay(swirl, slurry)
    # inner edge of the coping casts a thin shadow onto the slurry
    ring = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(15)))
    tint(ic, ring, None, (30, 12, 6), 0.45, 3)
    return slurry, iry


def tank(ic: Icon, x0: float, x1: float, y: float, depth: float, face: float, water, floor=None) -> Image.Image:
    """Rectangular brick settling tank from the raised camera: coping rim drawn in slight perspective
    (far edge narrower), water inside with a shaded far wall, brick front face. ``floor`` tints the
    settled clay seen through clear water. Returns the whole tank mask."""
    rim, inset = 18, 14
    top = [(x0 + inset, y), (x1 - inset, y), (x1, y + depth), (x0, y + depth)]
    whole = union(ic.poly_mask(top), ic.mask("rectangle", (x0, y + depth, x1, y + depth + face)))
    front = ic.mask("rectangle", (x0, y + depth, x1, y + depth + face))
    bricks(ic, front, (x0, y + depth, x1, y + depth + face), course=16, length=34)
    tint(ic, ic.mask("rectangle", (x1 - 50, y, x1 + 10, y + depth + face)), front, (20, 8, 4), 0.35, 14)
    tm = ic.poly_mask(top)
    ic.fill(tm, COPING, COPING_DK, (y, y + depth), noise=0.2)
    wpts = [(x0 + inset + rim, y + rim * 0.6), (x1 - inset - rim, y + rim * 0.6), (x1 - rim, y + depth - rim * 0.7),
            (x0 + rim, y + depth - rim * 0.7)]
    wm = ic.poly_mask(wpts)
    ic.fill(wm, water[0], water[1], (y, y + depth), noise=0.08, chroma=0.05)
    if floor is not None:  # settled clay seen on the floor near the front
        tint(ic, ic.mask("ellipse", (x0 + 40, y + depth * 0.45, x1 - 10, y + depth * 1.3)), wm, floor, 0.35, 14)
    tint(ic, ic.mask("rectangle", (x0, y, x1, y + 26)), wm, (20, 12, 8), 0.5, 6)  # far wall shadow
    tint(ic, ic.mask("rectangle", (x0, y + depth - 30, x1, y + depth)), wm, (255, 250, 236), 0.16, 8)  # near sky glint

    def glints(d: ImageDraw.ImageDraw) -> None:
        for _ in range(int((x1 - x0) / 34)):
            gx, gy = ic.random.uniform(x0 + 20, x1 - 40), ic.random.uniform(y + 30, y + depth - 14)
            d.line([(gx, gy), (gx + ic.random.uniform(20, 46), gy)], fill=(240, 240, 230, 130), width=4)

    ic.overlay(glints, wm)
    ic.outline(wpts, 3, (40, 24, 16, 120))
    ic.outline(top[:2] + [(x1, y + depth + face), (x0, y + depth + face)], 4, (40, 24, 16, 180))
    ic.line([(x0, y + depth), (x1, y + depth)], 4, (50, 30, 20, 160))
    ic.line([(x0 + 4, y + depth + 3), (x1 - 4, y + depth + 3)], 3, (255, 230, 200, 70))
    return whole


def spill(ic: Icon, x: float, y: float, dx: float, dy: float, color=(170, 120, 96)) -> None:
    """Thin stream of water pouring from a spout."""
    ts = np.linspace(0, 1, 12)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    c = tuple(color)
    ic.overlay(lambda d: (d.line(path, fill=c + (235,), width=16, joint="curve"),
                          d.line([(px - 2, py) for px, py in path], fill=(236, 226, 210, 170), width=6, joint="curve")))


def blob(ic: Icon, cx: float, cy: float, rx: float, ry: float, cut=None, embed: bool = False) -> Image.Image:
    """One sticky, rounded lump of wet clay: soft contour, radial light from the upper left, wet
    sheen, core shadow. ``cut`` = (angle, keep) chops it flat: the silhouette gets a straight edge at
    ``keep`` x radius along the angle and a smooth, lighter spade-cut face lies just inside it.
    ``embed`` fades the lower edge into the heap below (no rim there)."""
    R = ic.random
    a0 = R.uniform(0, 1)
    pts = smooth([(cx + math.cos(a0 + k * math.pi / 4) * rx * R.uniform(0.9, 1.08),
                   cy + math.sin(a0 + k * math.pi / 4) * ry * R.uniform(0.9, 1.08)) for k in range(8)], 3)
    m = ic.poly_mask(pts)
    edge = None
    if cut is not None:
        a, keep = cut
        nx, ny = math.cos(a), math.sin(a)
        r = math.hypot(rx * nx, ry * ny)
        px, py = cx + nx * r * keep, cy + ny * r * keep
        big = 2000
        half = [(px - ny * big, py + nx * big), (px + ny * big, py - nx * big),
                (px + ny * big - nx * big, py - nx * big - ny * big), (px - ny * big - nx * big, py + nx * big - ny * big)]
        m = ic.intersect(m, ic.poly_mask(half))
        fw = r * 0.42
        qx, qy = px - nx * fw, py - ny * fw
        band = [(qx - ny * big, qy + nx * big), (qx + ny * big, qy - nx * big), (px + ny * big, py - nx * big),
                (px - ny * big, py + nx * big)]
        edge = (ic.intersect(m, ic.poly_mask(band)), (qx, qy), (nx, ny), a)
    ic.fill(m, "#b25a3c", "#3e140a", radial=(cx - rx * 0.45, cy - ry * 0.6, max(rx, ry) * 1.9), noise=0.12, chroma=0.06)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.2, cy - ry * 0.1, cx + rx * 1.2, cy + ry * 1.2)), m, (30, 10, 4), 0.35, rx * 0.25)
    if edge is not None:  # flat spade-cut face: smoother, lit if it faces up, a crisp ridge line
        fm, (qx, qy), (nx, ny), a = edge
        lit = max(0.0, -ny * 0.8 - nx * 0.4)
        c1 = tuple(int(v) for v in np.array([196, 112, 78]) + lit * np.array([36, 30, 24]))
        ic.fill(fm, c1, "#a4583a", radial=(qx, qy, rx * 1.4), noise=0.03, chroma=0.02)
        ic.overlay(lambda d: d.line([(qx - ny * rx * 2, qy + nx * rx * 2), (qx + ny * rx * 2, qy - nx * rx * 2)],
                                    fill=(255, 220, 196, 110), width=3), m)
    # wet sheen on the upper-left bulge
    sx, sy = cx - rx * 0.35, cy - ry * 0.45
    tint(ic, ic.mask("ellipse", (sx - rx * 0.26, sy - ry * 0.14, sx + rx * 0.26, sy + ry * 0.14)), m, (255, 226, 206), 0.36, 5)
    if embed:
        tint(ic, ic.mask("rectangle", (cx - rx * 1.2, cy + ry * 0.3, cx + rx * 1.2, cy + ry * 1.2)), m, (40, 12, 4), 0.3, 10)
    else:
        ic.overlay(lambda d: d.line(pts + pts[:1], fill=(60, 24, 14, 90), width=3), m)
    return m


def clay_heap(ic: Icon, x0: float, x1: float, base: float, H: float) -> None:
    """Heap of sticky dug clay: a low mound body with rounded lumps piled on it back to front, three
    of them chopped by the spade into flat faces, soft shadow at the foot."""
    w = x1 - x0
    ts = np.linspace(0, 1, 40)
    dome = [(x0 + t * w, base - H * 0.62 * math.sin(math.pi * t) ** 0.7 * (1 - 0.15 * t)) for t in ts]
    m = ic.poly_mask(smooth([(x0, base)] + dome + [(x1, base)], 1))
    ic.fill(m, "#9a4428", "#300e06", (base - H * 0.62, base), noise=0.14, chroma=0.07)
    lumps = [  # (u, height above base as share of H, rx share of w, ry share of H, cut) back to front
        (0.44, 0.8, 0.19, 0.2, (-0.8, 0.55)),
        (0.22, 0.52, 0.19, 0.21, None), (0.66, 0.52, 0.2, 0.22, (-0.35, 0.5)),
        (0.12, 0.2, 0.13, 0.15, None), (0.4, 0.24, 0.21, 0.22, (-1.75, 0.55)), (0.8, 0.2, 0.15, 0.16, None),
    ]
    for u, v, rx, ry, cut in lumps:
        blob(ic, x0 + u * w, base - v * H, rx * w, ry * H, cut, embed=v > 0.3)
    tint(ic, ic.mask("rectangle", (x0 - 20, base - H * 0.16, x1 + 20, base + 10)), None, (24, 8, 4), 0.3, 14)


def ripple(ic: Icon, x: float, y: float, clip: Image.Image) -> None:
    """V-shaped wake trailing to the right of a tine dragged left through the slurry."""
    def paint(d: ImageDraw.ImageDraw) -> None:
        d.ellipse((x - 16, y - 6, x + 16, y + 8), fill=(80, 32, 18, 140))
        for k, a in enumerate((190, 150, 110)):
            d.line([(x + 8 + k * 16, y - 8 - k * 5), (x + 26 + k * 22, y - 12 - k * 8)], fill=(226, 170, 140, a), width=4)
            d.line([(x + 8 + k * 16, y + 8 + k * 5), (x + 26 + k * 22, y + 12 + k * 8)], fill=(226, 170, 140, a), width=4)
        d.arc((x - 20, y - 12, x + 12, y + 12), 90, 270, fill=(236, 190, 160, 170), width=4)

    ic.overlay(paint, clip)


# ---------------------------------------------------------------- drawing
def shed(ic: Icon) -> None:
    """Small plank wash house behind the pit on the left: tiled roof, open dark doorway."""
    x0, x1, eave, ridge, foot = 70, 380, 290, 150, 470
    planks(ic, [(x0 + 20, eave - 20), (x1 - 20, eave - 20), (x1 - 20, foot), (x0 + 20, foot)], "#8e7056", "#4c3a2a", 30)
    ic.rect((150, 336, 232, foot), "#221812", "#120c08", edge=4)  # open doorway
    ic.rect((280, 330, 330, 372), "#2a1e16", "#140e0a", edge=4)  # shutter opening
    ic.shade(ic.mask("rectangle", (x0, eave - 20, x1, eave + 40)), alpha=0.5, blur=10)
    shingles(ic, [(x0 - 12, eave), (x1 + 12, eave), (x1 - 28, ridge), (x0 + 28, ridge)], "#a8644a", "#6a3a2a",
             course=30, stagger=38)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86

    shed(ic)
    # two stepped settling tanks at the back right; the water clears as the clay settles
    tank(ic, 668, 880, 392, 112, 46, ("#ac6c50", "#6c3626"))
    tank(ic, 800, 1012, 462, 104, 44, ("#a2b6a6", "#566a60"), floor=(150, 96, 70))
    timber(ic, (852, 432), (888, 446), 20, "#7c5838", "#4a321f")  # spout from the upper tank
    spill(ic, 884, 446, 20, 38, (150, 150, 130))
    ic.shade(ic.mask("rectangle", (800, 462, 880, 560)), alpha=0.35, blur=14)  # upper tank shades the lower
    # launder from the pit rim to the upper tank
    timber(ic, (660, 440), (704, 446), 24, "#7c5838", "#4a321f")

    slurry, iry = cylinder(ic)

    # gin post with an iron collar; one thick sweep arm from the collar over the rim to the horse
    timber(ic, (PX, PY + 20), (PX, 226), 44, "#8e6644", "#4e3522")
    ic.fill(ic.mask("ellipse", (PX - 32, 208, PX + 32, 242)), "#a07650", "#5e4228", noise=0.2)
    arm0 = (PX, 470)
    arm1 = (HX + 30 * HS, GROUND - 232 * HS)
    ax, ay = arm1[0] - arm0[0], arm1[1] - arm0[1]
    # shadow of the arm on the slurry
    ic.shade(ic.intersect(slurry, ic.poly_mask([(arm0[0], arm0[1] + 40), (arm1[0], arm1[1] + 40), (arm1[0], arm1[1] + 64),
                                                (arm0[0], arm0[1] + 64)])), (30, 12, 6), 0.4, blur=8)
    # harrow tines hanging from the arm into the slurry, each with a wake behind it
    tines = []
    for t in (0.14, 0.3, 0.46):
        tx, ty = arm0[0] + ax * t, arm0[1] + ay * t
        tines.append((tx, ty))
        timber(ic, (tx, ty), (tx - 4, ty + 44), 14, "#6e4e32", "#3e2a1a")
        ripple(ic, tx - 4, ty + 46, slurry)
    timber(ic, arm0, arm1, 36)
    ic.fill(ic.mask("rectangle", (PX - 26, 452, PX + 26, 490)), "#5a5456", "#262224", noise=0.1)  # post collar
    ic.line([(PX - 22, 458), (PX - 22, 484)], 3, (170, 166, 160, 150))
    for tx, ty in tines:  # iron straps holding the tines
        ic.line([(tx - 10, ty - 12), (tx - 10, ty + 16)], 5, (60, 56, 56, 220))

    # heap of dug clay, front left, with a spade stuck in it
    clay_heap(ic, 14, 380, GROUND - 4, 250)
    timber(ic, (172, 560), (148, 700), 22, "#9a7650", "#5a4028")
    ic.line([(158, 564), (188, 556)], 12, (106, 80, 54))  # T-grip
    ic.poly([(126, 690), (170, 696), (166, 750), (148, 762), (126, 748)], "#6e6a66", "#34302e", edge=4)
    blob(ic, 360, GROUND - 22, 34, 22)  # loose lumps at the foot
    blob(ic, 40, GROUND - 16, 28, 18)

    # the horse walking round in front of the pit, hitched to the arm
    ic.shade(ic.mask("ellipse", (420, GROUND - 28, 990, GROUND + 22)), alpha=0.45, blur=12)
    horse(ic, HX, GROUND, HS)
