"""Cookshop (cookshop, formerly cookery): stone cookhouse with an open hearth, hanging cauldron and larder.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/cookshop/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/cookshop

Identity: the glowing arched hearth with an iron cauldron hanging over the fire, the big smoking
chimney above it, and hams and a string of sausages hanging in the open larder shed on the right.
Supporting props: bread on the serving-hatch sill, sealed crocks of victuals, a firewood stack and
a barrel. Local helpers (not in the kit): ``stones`` (blocks shaded as forms instead of outlined),
``tint`` (blurred colour patch clipped to a mask),
``shingles`` (per-tile tone, lit lip and course shadow), ``smoke``, ``flame``, ``ham``, ``sausages``,
``loaf``, ``crock``, ``log_end``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 5
REFS = ("granary", "pirate_tavern", "brewery", "market_village")

BASE = 900
L, R = 110, 650  # main cookhouse walls
EAVE, RIDGE = 462, 292
BAND = 566  # bottom of the timber-framed upper band
AX0, AX1, ATOP = 212, 468, 606  # hearth arch opening
AW = AX1 - AX0
ACX = (AX0 + AX1) / 2
LX0, LX1, LTOP, LFRONT = 650, 912, 506, 616  # larder lean-to
IRON = (34, 31, 30)
TIMBER = (110, 76, 50)


# ---------------------------------------------------------------- helpers (candidates for the kit)
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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines. One blended layer, so it is cheap."""
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


def smoke(ic: Icon, puffs) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, "#e8e4dc", "#8e8a84", radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#ffbe55", "#c9451c"), inner=("#fff3c4", "#ffb449")) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one. No edge lines."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (inner, 0.5, 0.62)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def ham(ic: Icon, top, w, h, skin=("#b6623e", "#46180d")) -> None:
    """Cured ham hanging from its hock: pear-shaped, lit upper left, twine at the hock, bone knob."""
    cx, ty = top
    ss = np.linspace(0, 1, 30)
    hw = [w / 2 * (0.2 + 0.8 * math.sqrt(max(math.sin(math.pi * s ** 1.4), 0))) for s in ss]
    left = [(cx - v + 6 * s, ty + h * s) for s, v in zip(ss, hw)]
    right = [(cx + v + 6 * s, ty + h * s) for s, v in zip(ss, hw)]
    pts = left + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, skin[0], skin[1], radial=(cx - w * 0.3, ty + h * 0.35, h * 0.95), noise=0.18)
    tint(ic, ic.mask("ellipse", (cx - w * 0.05, ty + h * 0.2, cx + w * 0.9, ty + h * 1.1)), m, (20, 6, 2), 0.35, 10)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, ty + h * 0.42, cx - w * 0.08, ty + h * 0.72)), m, (255, 222, 190),
         0.28, 8)
    for f in (0.12, 0.2):
        y = ty + h * f
        ic.line([(cx - w * 0.16, y), (cx + w * 0.18, y + 3)], 4, (60, 44, 28, 220))
    ic.ellipse((cx - w * 0.13, ty - 10, cx + w * 0.13, ty + 10), "#eadfc4", "#a89a7c", edge=3)
    ic.outline(pts, 4, (50, 22, 12, 170))


def sausages(ic: Icon, p0, p1, sag, n, th=22, skin=("#b85c40", "#4c1a0e")) -> None:
    """A drooping string of sausage links between two points."""
    def at(t):
        return (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t + sag * 4 * t * (1 - t))

    for i in range(n):
        a, b = at(i / n), at((i + 1) / n)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) * 0.56
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        local = [(math.cos(t) * ln, math.sin(t) * th / 2) for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        pts = ic.rotate(local, (cx, cy), ang)
        ic.fill(ic.poly_mask(pts), skin[0], skin[1], radial=(cx - ln * 0.5, cy - th * 0.6, ln * 1.6), noise=0.15)
        ic.outline(pts, 3, (50, 20, 10, 160))
        ic.line([(cx - ln * 0.4, cy - th * 0.18), (cx + ln * 0.1, cy - th * 0.24)], 3, (240, 190, 160, 110))
    for i in range(n + 1):
        x, y = at(i / n)
        ic.draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(70, 52, 34, 255))


def loaf(ic: Icon, cx, base, w, h) -> None:
    """Round loaf: golden dome lit from the upper left with two score cuts."""
    pts = [(cx + math.cos(a) * w / 2, base + math.sin(a) * h) for a in np.linspace(math.pi, 2 * math.pi, 20)]
    pts += [(cx + w * 0.46, base + 4), (cx - w * 0.46, base + 4)]
    ic.fill(ic.poly_mask(pts), "#e0ae6a", "#74441c", radial=(cx - w * 0.22, base - h * 0.85, w * 0.95), noise=0.12)
    for dx in (-0.14, 0.12):
        x = cx + w * dx
        ic.line([(x - w * 0.08, base - h * 0.45), (x + w * 0.08, base - h * 0.8)], 3, (110, 64, 26, 200))
    ic.outline(pts, 3, (60, 34, 14, 170))


def crock(ic: Icon, cx, base, w, h, body=("#a98a6a", "#4a3727"), cloth=("#ddd0b4", "#978667")) -> None:
    """Stoneware crock sealed with a tied cloth: preserved victuals."""
    knots = [(0, 0.30), (0.1, 0.31), (0.2, 0.44), (0.38, 0.5), (0.62, 0.49), (0.9, 0.42), (1.0, 0.37)]
    ss = np.linspace(0, 1, 26)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    ty = base - h
    pts = [(cx - v, ty + h * s) for s, v in zip(ss, hw)] + [(cx + v, ty + h * s) for s, v in zip(ss[::-1], hw[::-1])]
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - w * 0.28, ty + h * 0.4, w * 1.05), noise=0.14)
    tint(ic, ic.mask("rectangle", (cx + w * 0.12, ty, cx + w, base)), m, (20, 12, 6), 0.3, 12)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, ty + h * 0.3, cx - w * 0.2, ty + h * 0.62)), m, (255, 240, 220),
         0.3, 5)
    ic.line([(cx - w * 0.47, ty + h * 0.42), (cx + w * 0.47, ty + h * 0.44)], 3, (60, 40, 24, 120))
    ic.outline(pts, 4, (44, 30, 20, 170))
    lid = [(cx - w * 0.38, ty + h * 0.2), (cx - w * 0.36, ty + h * 0.04), (cx - w * 0.2, ty - h * 0.08),
           (cx + w * 0.02, ty - h * 0.11), (cx + w * 0.24, ty - h * 0.07), (cx + w * 0.37, ty + h * 0.04),
           (cx + w * 0.4, ty + h * 0.22), (cx + w * 0.1, ty + h * 0.16), (cx - w * 0.12, ty + h * 0.23)]
    ic.fill(ic.poly_mask(lid), cloth[0], cloth[1], radial=(cx - w * 0.2, ty - h * 0.08, w * 0.8), noise=0.1)
    ic.outline(lid, 3, (70, 58, 40, 170))
    ic.line([(cx - w * 0.34, ty + h * 0.08), (cx + w * 0.35, ty + h * 0.09)], 5, (92, 62, 38))


def log_end(ic: Icon, cx, cy, r) -> None:
    """Sawn log end: bark ring, pale end grain lit from the upper left, one growth ring."""
    ic.fill(ic.mask("ellipse", (cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5)), "#6a4a30", "#2e1e12", (cy - r, cy + r))
    k = ic.random.uniform(0.78, 1.05)
    lite, dark = tuple(int(v * k) for v in (216, 178, 124)), tuple(int(v * k) for v in (138, 94, 50))
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), lite, dark,
            radial=(cx - r * 0.4, cy - r * 0.5, r * 2.0), noise=0.14)
    if ic.random.random() < 0.35:  # weathered grey end
        ic.shade(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), (120, 116, 108), 0.35)
    ic.overlay(lambda d: d.arc((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), 200, 470,
                               fill=(120, 80, 40, 70), width=2))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86  # keep the fire glow and cured meat warm after grading
    # ---- smoke from the chimney, behind everything (drifts right and flattens)
    smoke(ic, [(596, 70, 26), (556, 60, 36), (500, 62, 46), (440, 78, 54), (386, 104, 52), (346, 138, 44)])

    # ---- larder lean-to, back parts
    back = ic.mask("rectangle", (LX0, LTOP, LX1, BASE))
    stones(ic, (LX0, LTOP, LX1, BASE), "#6a5c4e", "#3a3028", course=34, lit=35, shadow=110, moss=0.05)
    tint(ic, ic.mask("rectangle", (LX0, LTOP, LX1, LTOP + 260)), back, (8, 4, 2), 0.55, 30)
    lroof = [(LX0 - 4, LTOP), (LX1 + 6, LTOP), (LX1 + 34, LFRONT), (LX0 - 8, LFRONT)]
    shingles(ic, lroof, "#8a7560", "#54463a", course=24, stagger=30, edge=6)
    tint(ic, ic.poly_mask([(LX0, LTOP), (LX0 + 90, LTOP), (LX0 + 60, LFRONT), (LX0, LFRONT)]), ic.poly_mask(lroof),
         (0, 0, 0), 0.35, 14)

    # ---- main roof: weathered clay tiles, slightly sagging ridge
    roof = [(84, EAVE + 10), (678, EAVE + 10), (634, RIDGE), (380, RIDGE + 7), (130, RIDGE)]
    rmask = shingles(ic, roof, "#9a604a", "#4e2e20", course=32, stagger=44)
    for _ in range(14):
        x, y = ic.random.uniform(120, 660), ic.random.uniform(RIDGE, EAVE)
        r = ic.random.uniform(24, 60)
        col = ic.random.choice([(0, 0, 0), (255, 232, 200), (84, 92, 46)])
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), rmask, col,
             ic.random.uniform(0.08, 0.18), 14)
    tint(ic, ic.poly_mask([(470, RIDGE), (700, RIDGE), (700, EAVE + 12), (520, EAVE + 12)]), rmask, (0, 0, 0), 0.18, 50)
    ridge = [(128, RIDGE - 12), (380, RIDGE - 5), (636, RIDGE - 12), (636, RIDGE + 6), (380, RIDGE + 13), (128, RIDGE + 6)]
    ic.poly(ridge, "#8e5c46", "#5c3828", edge=4)

    # ---- chimney stack rising through the roof, above the hearth
    cx0, cx1, ctop, cbot = 286, 398, 176, 376
    tint(ic, ic.poly_mask([(cx1, ctop + 30), (cx1 + 60, ctop + 70), (cx1 + 70, cbot + 30), (cx1, cbot)]), rmask,
         (0, 0, 0), 0.4, 12)
    cmask = ic.mask("rectangle", (cx0, ctop, cx1, cbot))
    stones(ic, (cx0, ctop, cx1, cbot), "#ac9e8a", "#6e6254", course=30)
    tint(ic, ic.mask("rectangle", (cx0 + 70, ctop, cx1 + 20, cbot)), cmask, (0, 0, 0), 0.32, 16)
    tint(ic, ic.mask("rectangle", (cx0, ctop, cx1, ctop + 50)), cmask, (20, 14, 10), 0.35, 14)  # soot
    ic.outline([(cx0, ctop), (cx1, ctop), (cx1, cbot), (cx0, cbot)], 4)
    ic.rect((cx0 - 8, cbot - 14, cx1 + 8, cbot + 4), "#6e6a66", "#4a4644", edge=4)  # lead flashing
    ic.poly([(cx0 - 14, 152), (cx1 + 14, 152), (cx1 + 14, 180), (cx0 - 14, 180)], "#b4a896", "#7c7266", edge=4)
    ic.poly([(cx0 - 6, 140), (cx1 + 6, 140), (cx1 + 14, 152), (cx0 - 14, 152)], "#c2b6a4", "#9a8e7e", edge=4)
    ic.ellipse((cx0 + 22, 141, cx1 - 22, 151), "#1c1410", "#0c0806", edge=0)

    # ---- timber-framed upper band
    ic.plaster_frame((L, EAVE, R, BAND), posts=(L + 12, 204, 336, 474, R - 12),
                     braces=(((336, BAND), (474, EAVE)),), wall="#d2bc96", wall_dark="#a88e6a")
    ic.window(248, 494, 294, 538)
    ic.window(534, 492, 584, 538)
    tint(ic, ic.mask("rectangle", (L, EAVE, R, EAVE + 44)), None, (0, 0, 0), 0.42, 10)

    # ---- stone ground floor
    wall = ic.mask("rectangle", (L, BAND, R, BASE))
    stones(ic, (L, BAND, R, BASE), "#a39280", "#6c5e50", course=40)
    tint(ic, ic.mask("rectangle", (L, BASE - 90, R, BASE)), wall, (40, 44, 20), 0.22, 24)  # grime and moss low
    tint(ic, ic.mask("rectangle", (R - 80, BAND, R + 40, BASE)), wall, (0, 0, 0), 0.16, 30)
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(16):
        x = ic.random.uniform(L + 10, R - 10)
        sd.line([(x, BAND), (x + ic.random.uniform(-4, 4), BAND + ic.random.uniform(40, 130))], fill=255,
                width=int(ic.random.uniform(4, 10)))
    tint(ic, streaks, wall, (30, 24, 16), 0.22, 4)
    ic.rect((L - 10, BAND - 12, R + 10, BAND + 10), "#6e4c32", "#48301f")  # jetty beam
    tint(ic, ic.mask("rectangle", (L, BAND + 10, R, BAND + 46)), wall, (0, 0, 0), 0.4, 10)
    ic.outline([(L, BAND), (R, BAND), (R, BASE), (L, BASE)], 5)

    # ---- the hearth: dressed-stone arch, soot above, fire and cauldron inside
    opening = union(ic.mask("ellipse", (AX0, ATOP, AX1, ATOP + AW)),
                    ic.mask("rectangle", (AX0, ATOP + AW / 2, AX1, BASE)))
    p = 32
    ring = union(ic.mask("ellipse", (AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p)),
                 ic.mask("rectangle", (AX0 - p, ATOP + AW / 2, AX1 + p, BASE)))
    ic.fill(ring, "#bcae98", "#7c7062", (ATOP - p, BASE), noise=0.16)
    cy = ATOP + AW / 2

    def joints(d: ImageDraw.ImageDraw) -> None:
        r0, r1 = AW / 2, AW / 2 + p
        for a in np.linspace(math.pi, 2 * math.pi, 10)[1:-1]:
            c, s = math.cos(a), math.sin(a)
            d.line([(ACX + c * r0, cy + s * r0), (ACX + c * r1, cy + s * r1)], fill=(40, 30, 22, 150), width=4)
            d.line([(ACX + c * r0 - 4, cy + s * r0), (ACX + c * r1 - 4, cy + s * r1)], fill=(255, 245, 225, 60), width=3)
        for y in np.arange(cy + 44, BASE, 46):
            for x0, x1 in ((AX0 - p, AX0), (AX1, AX1 + p)):
                d.line([(x0, y), (x1, y)], fill=(40, 30, 22, 150), width=4)
                d.line([(x0, y + 4), (x1, y + 4)], fill=(255, 245, 225, 55), width=3)

    ic.overlay(joints, ring)
    ic.overlay(lambda d: d.arc((AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p), 180, 360, fill=(40, 28, 20, 190),
                               width=5))
    tint(ic, ic.mask("ellipse", (ACX - 150, ATOP - 150, ACX + 150, ATOP + 60)), wall, (18, 12, 8), 0.45, 34)

    with ic.clipped(opening):
        ic.fill(opening, "#24160e", "#0c0604", (ATOP, BASE), noise=0.12)
        for y in np.arange(ATOP + 60, BASE, 34):  # sooty fire-back courses
            ic.line([(AX0, y), (AX1, y + 2)], 3, (10, 6, 4, 140))
        tint(ic, ic.mask("ellipse", (ACX - 170, BASE - 120, ACX + 170, BASE + 90)), None, (255, 120, 36), 0.62, 34)
        # chain and bail
        ic.line([(ACX, ATOP), (ACX, 738)], 8, IRON)
        for y in range(ATOP + 12, 736, 18):
            ic.draw.ellipse((ACX - 5, y - 6, ACX + 5, y + 6), outline=(70, 62, 58, 255), width=3)
        ic.draw.arc((ACX - 84, 736, ACX + 84, 834), 180, 360, fill=IRON + (255,), width=8)
        # logs and the flames behind the pot
        ic.beam((ACX - 116, 898), (ACX + 70, 878), 20, (74, 46, 26))
        ic.beam((ACX - 60, 876), (ACX + 120, 898), 20, (64, 40, 22))
        for fx, fw, fh, ln in ((-100, 48, 116, -14), (-62, 54, 80, 4), (56, 54, 88, -4), (98, 50, 124, 14)):
            flame(ic, ACX + fx, 896, fw, fh, ln)
        # cauldron
        pot = ic.intersect(ic.mask("ellipse", (ACX - 96, 740, ACX + 96, 876)),
                           ic.mask("rectangle", (0, 780, ic.size, ic.size)))
        ic.fill(pot, "#6e6862", "#121010", radial=(ACX - 50, 792, 160), noise=0.10)
        tint(ic, ic.mask("ellipse", (ACX - 104, 846, ACX + 104, 920)), pot, (255, 120, 40), 0.55, 10)
        tint(ic, ic.mask("ellipse", (ACX - 72, 794, ACX - 40, 842)), pot, (225, 214, 200), 0.32, 6)
        ic.line([(ACX - 86, 802), (ACX + 86, 804)], 4, (20, 18, 18, 150))
        ic.fill(ic.mask("ellipse", (ACX - 84, 768, ACX + 84, 792)), "#6a625c", "#2a2624", (768, 792), noise=0.08)
        ic.fill(ic.mask("ellipse", (ACX - 70, 772, ACX + 70, 788)), "#a8783e", "#5a3a1c", (772, 788), noise=0.12)
        for x in (ACX - 86, ACX + 82):
            ic.draw.ellipse((x - 7, 773, x + 7, 787), fill=IRON + (255,))
        # steam rising from the pot
        steam = Image.new("L", (ic.size, ic.size), 0)
        sd = ImageDraw.Draw(steam)
        sd.line([(ACX - 20, 772), (ACX - 34, 728), (ACX - 12, 690), (ACX - 30, 646)], fill=255, width=16, joint="curve")
        sd.line([(ACX + 22, 772), (ACX + 36, 720), (ACX + 18, 682)], fill=255, width=12, joint="curve")
        ic.shade(steam, (236, 228, 214), 0.45, blur=7)
        # small flames licking the pot bottom, embers
        for fx, fw, fh, ln in ((-40, 40, 40, -6), (-6, 46, 30, 4), (30, 40, 44, 8)):
            flame(ic, ACX + fx, 898, fw, fh, ln)
        fire = ic.mask("ellipse", (ACX - 130, 856, ACX + 130, 920))
        ic.shade(fire, (255, 190, 90), 0.3, blur=16)
        for _ in range(9):
            x, y = ACX + ic.random.uniform(-100, 100), ic.random.uniform(884, 898)
            ic.draw.ellipse((x - 5, y - 4, x + 5, y + 4), fill=(255, 200, 110, 255))
    # fire light on the arch jambs and the hearthstone
    tint(ic, ic.mask("ellipse", (ACX - 220, BASE - 200, ACX + 220, BASE + 60)), ring, (255, 140, 50), 0.28, 30)

    # ---- serving hatch with a propped shutter and bread on the sill
    ic.rect((544, 652, 624, 742), "#2e2016", "#140c08", noise=0.1)
    tint(ic, ic.mask("rectangle", (544, 652, 624, 690)), None, (0, 0, 0), 0.4, 8)
    shutter = [(532, 604), (636, 604), (642, 650), (526, 650)]
    ic.poly(shutter, "#8a6242", "#5a3c24", edge=4)
    for x in (560, 586, 612):
        ic.line([(x, 606), (x + 2, 648)], 3, (60, 40, 24, 150))
    tint(ic, ic.mask("rectangle", (530, 650, 640, 680)), None, (0, 0, 0), 0.35, 8)
    ic.line([(538, 650), (552, 740)], 7, (90, 62, 40))  # prop stick
    ic.rect((530, 740, 640, 758), "#9a6e48", "#5e3f26", edge=4)
    tint(ic, ic.mask("rectangle", (530, 758, 640, 790)), wall, (0, 0, 0), 0.35, 8)
    loaf(ic, 566, 742, 50, 30)
    loaf(ic, 610, 742, 42, 24)

    # ---- larder lean-to front: plate, post, hanging hams and sausages, crocks
    for cx, w, h in ((748, 60, 80), (820, 70, 96)):
        crock(ic, cx, BASE, w, h, body=("#8a7058", "#3a2a1e"), cloth=("#bcae92", "#7a6c54"))
    tint(ic, ic.mask("rectangle", (LX0, BASE - 110, LX1, BASE)), back, (0, 0, 0), 0.25, 20)
    for x, top in ((706, 646), (866, 640)):
        ic.line([(x, LFRONT + 20), (x, top)], 4, (70, 54, 36))
    ic.line([(772, LFRONT + 20), (772, 646)], 4, (70, 54, 36))
    for x, w, h in ((706, 74, 128), (866, 64, 112)):  # cast shadows of the hams on the back wall
        tint(ic, ic.mask("ellipse", (x - w * 0.3, 700, x + w * 0.9, 648 + h + 26)), back, (0, 0, 0), 0.35, 10)
    sausages(ic, (730, 648), (850, 644), 64, 6)
    ham(ic, (706, 648), 74, 128)
    ham(ic, (866, 642), 64, 112, skin=("#a8583a", "#40160c"))
    ic.beam((LX0 - 4, LFRONT + 12), (LX1 + 18, LFRONT + 12), 22, (104, 72, 46))
    ic.beam((LX1 - 6, LFRONT + 20), (LX1 - 10, BASE), 26, (104, 72, 46))
    tint(ic, ic.mask("rectangle", (LX1 + 4, LFRONT + 24, LX1 + 14, BASE)), None, (0, 0, 0), 0.3, 4)

    # ---- plinth and hearthstone, lit by the fire
    stones(ic, (L - 8, BASE - 14, LX1 + 10, BASE + 12), "#867a6a", "#5a5046", course=26, moss=0.0)
    ic.outline([(L - 8, BASE - 14), (LX1 + 10, BASE - 14), (LX1 + 10, BASE + 12), (L - 8, BASE + 12)], 4)
    tint(ic, ic.mask("ellipse", (ACX - 200, BASE - 40, ACX + 200, BASE + 50)), None, (255, 150, 60), 0.35, 16)

    # ---- firewood stack against the left wall
    stack = [(22, 918), (26, 790), (70, 760), (170, 752), (206, 780), (206, 918)]
    ic.poly(stack, "#4a3220", "#24160c", edge=0)
    rows = ((898, (42, 82, 122, 162, 196)), (862, (60, 100, 140, 180)), (826, (46, 86, 126, 166)),
            (790, (78, 118, 158)))
    for y, xs in rows:
        for x in xs:
            log_end(ic, x + ic.random.uniform(-4, 4), y + ic.random.uniform(-4, 4), ic.random.uniform(15, 23))
    tint(ic, ic.mask("rectangle", (150, 740, 240, 930)), ic.poly_mask(stack), (0, 0, 0), 0.25, 20)

    # ---- props bottom right: barrel and a sealed crock of victuals
    ic.barrel(912, 792, 1008, 962)
    tint(ic, ic.mask("rectangle", (960, 780, 1030, 980)), None, (0, 0, 0), 0.22, 12)
    crock(ic, 872, 972, 84, 110)
