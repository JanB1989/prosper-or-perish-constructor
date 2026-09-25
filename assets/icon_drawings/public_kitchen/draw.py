"""Public Kitchen (public_kitchen): a large civic town kitchen, the big upgrade of the Cookshop.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/public_kitchen/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/public_kitchen

Identity: a long two-storey sandstone hall under a slate roof with three smoking chimneys, its
ground floor an open three-bay serving arcade with a long counter carrying big steaming copper
pots. A gabled entrance block on the left, a trestle table with a bench in front of it, and grain
sacks with a basket of loaves bottom right. Distinct from the Cookshop (small grey cookhouse, one
fire arch, hams in a lean-to): bigger, paler, orderly arcade, copper instead of fire and meat.

Helpers copied from the Cookshop so the food family shares one finish: ``union``, ``tint``,
``stones``, ``shingles``, ``smoke``, ``loaf``. New local helpers: ``copper_pot``, ``steam``,
``grain_sack``, ``bowl``, ``jug``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("guild_hall", "hospital", "granary", "market_village")

BASE = 900
GX0, GX1, GCX = 60, 330, 195  # gabled entrance block
GAPEX, GEAVE = 142, 440
WX0, WX1, WEAVE, WRIDGE = 330, 900, 446, 290  # long arcaded wing
BAND = 600  # string course between the storeys
ATOP = 634
ARCHES = ((364, 504), (548, 690), (734, 872))
CT = 806  # counter top
STONE = ("#bfa276", "#7c6246")
DRESSED = ("#d8c6a2", "#9c8866")
SLATE = ("#7d7a7a", "#3e3c40")
IRON = (34, 31, 30)


# ---------------------------------------------------------------- helpers (shared with the Cookshop)
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


def loaf(ic: Icon, cx, base, w, h) -> None:
    """Round loaf: golden dome lit from the upper left with two score cuts."""
    pts = [(cx + math.cos(a) * w / 2, base + math.sin(a) * h) for a in np.linspace(math.pi, 2 * math.pi, 20)]
    pts += [(cx + w * 0.46, base + 4), (cx - w * 0.46, base + 4)]
    ic.fill(ic.poly_mask(pts), "#e0ae6a", "#74441c", radial=(cx - w * 0.22, base - h * 0.85, w * 0.95), noise=0.12)
    for dx in (-0.14, 0.12):
        x = cx + w * dx
        ic.line([(x - w * 0.08, base - h * 0.45), (x + w * 0.08, base - h * 0.8)], 3, (110, 64, 26, 200))
    ic.outline(pts, 3, (60, 34, 14, 170))


# ---------------------------------------------------------------- local helpers
def profile(cx, top, h, w, knots, n=28):
    """Closed outline of a turned vessel from (s, half-width fraction) knots, s = 0 at the top."""
    ss = np.linspace(0, 1, n)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    return [(cx - v, top + h * s) for s, v in zip(ss, hw)] + [(cx + v, top + h * s) for s, v in zip(ss[::-1], hw[::-1])]


def copper_pot(ic: Icon, cx, base, w, h, lid=False, stew=("#b87a3e", "#5a3018"),
               body=("#eaa46a", "#4c1c0c")) -> None:
    """Big copper cooking pot: burnished body lit upper left with a vertical specular streak,
    rolled rim, iron ring handles, stew or a domed lid on top."""
    top = base - h
    pts = profile(cx, top, h, w, [(0, 0.47), (0.12, 0.5), (0.5, 0.53), (0.82, 0.48), (1, 0.38)])
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - w * 0.26, top + h * 0.38, w * 1.0), noise=0.10, chroma=0.05)
    tint(ic, ic.mask("rectangle", (cx + w * 0.14, top, cx + w, base)), m, (24, 8, 4), 0.35, 14)
    tint(ic, ic.mask("ellipse", (cx - w * 0.36, top + h * 0.2, cx - w * 0.22, top + h * 0.8)), m, (255, 236, 200),
         0.55, 5)
    tint(ic, ic.mask("ellipse", (cx + w * 0.26, top + h * 0.3, cx + w * 0.42, top + h * 0.7)), m, (255, 180, 120),
         0.22, 6)  # warm bounce light
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.2, cx + w, base + 4)), m, (18, 6, 2), 0.35, 8)
    ic.line([(cx - w * 0.5, top + h * 0.3), (cx + w * 0.5, top + h * 0.32)], 3, (70, 26, 10, 140))
    ic.outline(pts, 4, (54, 22, 10, 190))
    for sx in (-1, 1):
        hx = cx + sx * w * 0.53
        ic.overlay(lambda d, hx=hx: d.ellipse((hx - 11, top + h * 0.14, hx + 11, top + h * 0.4),
                                               outline=IRON + (255,), width=6))
    rim = (cx - w * 0.52, top - h * 0.1, cx + w * 0.52, top + h * 0.1)
    ic.fill(ic.mask("ellipse", rim), "#f2bc84", "#7a3a18", radial=(cx - w * 0.3, top - h * 0.1, w * 0.9), noise=0.08)
    ic.overlay(lambda d: d.ellipse(rim, outline=(54, 22, 10, 190), width=4))
    inner = (cx - w * 0.44, top - h * 0.065, cx + w * 0.44, top + h * 0.075)
    if lid:
        dome = [(cx + math.cos(a) * w * 0.46, top + 2 + math.sin(a) * h * 0.26)
                for a in np.linspace(math.pi, 2 * math.pi, 24)]
        ic.fill(ic.poly_mask(dome), "#e6a26a", "#6a2c12", radial=(cx - w * 0.2, top - h * 0.24, w * 0.7), noise=0.1)
        ic.outline(dome, 4, (54, 22, 10, 190))
        ic.ellipse((cx - 9, top - h * 0.3 - 8, cx + 9, top - h * 0.3 + 8), "#5a4a40", "#1e1814", edge=3)
    else:
        ic.fill(ic.mask("ellipse", inner), stew[0], stew[1], (inner[1], inner[3]), noise=0.2)
        tint(ic, ic.mask("ellipse", (inner[0], inner[1], inner[2], inner[1] + 10)), ic.mask("ellipse", inner),
             (20, 8, 4), 0.5, 3)


def quoins(ic: Icon, x, y0, y1, side: int, h: float = 46) -> None:
    """Dressed corner stones, alternately long and short, laid inwards from the corner ``x``."""
    y, k = y1 - h, 0
    while y > y0 - h * 0.5:
        w = (54 if k % 2 else 34) * ic.random.uniform(0.92, 1.08)
        xa, xb = sorted((x, x + side * w))
        top = max(y, y0)
        b = (xa + 2, top + 2, xb - 2, y + h - 2)
        m = ic.mask("rectangle", b)
        ic.fill(m, DRESSED[0], DRESSED[1], (top, y + h), noise=0.14)
        ic.line([(b[0], b[3]), (b[0], b[1]), (b[2], b[1])], 4, (255, 246, 226, 90))
        ic.line([(b[2], b[1]), (b[2], b[3]), (b[0], b[3])], 5, (40, 28, 18, 150))
        y -= h
        k += 1


def steam(ic: Icon, paths, alpha=0.5) -> None:
    """Soft rising steam: thick blurred wisps along the given polylines."""
    lay = Image.new("L", (ic.size, ic.size), 0)
    d = ImageDraw.Draw(lay)
    for pts, w in paths:
        d.line(pts, fill=255, width=w, joint="curve")
    ic.shade(lay, (238, 232, 222), alpha, blur=8)


def grain_sack(ic: Icon, cx, base, w, h, open_top=False, col=("#d9c496", "#6e5a3a")) -> None:
    """Burlap sack, lumpy and lit upper left; either tied at the neck or rolled open showing grain."""
    top = base - h
    if open_top:
        knots = [(0, 0.40), (0.1, 0.45), (0.5, 0.52), (0.85, 0.5), (1, 0.46)]
    else:
        knots = [(0, 0.16), (0.08, 0.2), (0.16, 0.13), (0.3, 0.36), (0.6, 0.5), (0.9, 0.5), (1, 0.44)]
    pts = profile(cx, top, h, w, knots, 30)
    pts = [(x + ic.random.uniform(-2, 2), y + ic.random.uniform(-2, 2)) for x, y in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, col[0], col[1], radial=(cx - w * 0.28, top + h * 0.35, w * 1.0), noise=0.12, chroma=0.05)
    tint(ic, ic.mask("rectangle", (cx + w * 0.1, top, cx + w, base)), m, (20, 12, 4), 0.3, 16)
    folds = Image.new("L", (ic.size, ic.size), 0)
    fd = ImageDraw.Draw(folds)
    for f in (-0.22, 0.05, 0.28):
        x = cx + w * f
        fd.line([(x, top + h * 0.35), (x + w * 0.06, base - h * 0.08)], fill=255, width=6)
    tint(ic, folds, m, (40, 26, 12), 0.3, 5)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.14, cx + w, base + 4)), m, (20, 12, 4), 0.35, 8)
    ic.outline(pts, 4, (60, 44, 26, 180))
    if open_top:
        rim = (cx - w * 0.44, top - h * 0.1, cx + w * 0.44, top + h * 0.12)
        ic.fill(ic.mask("ellipse", rim), "#e2cfa2", "#8a7450", (rim[1], rim[3]), noise=0.2)
        heap = [(cx + math.cos(a) * w * 0.38, top + 2 + math.sin(a) * h * 0.2) for a in np.linspace(math.pi, 2 * math.pi, 20)]
        ic.fill(ic.poly_mask(heap), "#f0cc70", "#9a6e24", radial=(cx - w * 0.15, top - h * 0.18, w * 0.6), noise=0.35)
        ic.outline(heap, 3, (110, 76, 24, 150))
    else:
        ic.line([(cx - w * 0.17, top + h * 0.14), (cx + w * 0.17, top + h * 0.15)], 6, (84, 60, 34))


def bowl(ic: Icon, cx, base, w, h, col=("#a67a50", "#4e321c")) -> None:
    """Turned wooden bowl seen from slightly above."""
    top = base - h
    pts = [(cx + math.cos(a) * w / 2, top + math.sin(a) * h) for a in np.linspace(0, math.pi, 16)]
    ic.fill(ic.poly_mask(pts), col[0], col[1], radial=(cx - w * 0.25, top, w * 0.8), noise=0.12)
    ic.ellipse((cx - w / 2, top - h * 0.25, cx + w / 2, top + h * 0.25), "#5a3a20", "#3a2412", edge=3)


def jug(ic: Icon, cx, base, w, h, col=("#b89a76", "#54402c")) -> None:
    """Glazed earthenware jug with a handle."""
    top = base - h
    pts = profile(cx, top, h, w, [(0, 0.26), (0.12, 0.22), (0.3, 0.3), (0.65, 0.5), (0.9, 0.46), (1, 0.38)])
    ic.overlay(lambda d: d.arc((cx + w * 0.2, top + h * 0.12, cx + w * 0.72, top + h * 0.6), 270, 90,
                               fill=(80, 60, 40, 255), width=8))
    ic.fill(ic.poly_mask(pts), col[0], col[1], radial=(cx - w * 0.2, top + h * 0.4, w * 0.9), noise=0.14)
    ic.outline(pts, 3, (50, 36, 22, 180))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.84  # keep the copper warm after grading

    # ---- smoke from the three chimneys, behind everything (drifts right)
    smoke(ic, [(916, 100, 30), (880, 116, 28), (848, 140, 24), (818, 164, 20)])
    smoke(ic, [(636, 66, 42), (588, 80, 38), (544, 102, 34), (506, 126, 28), (478, 150, 22)])
    smoke(ic, [(368, 32, 38), (324, 44, 34), (288, 64, 28), (262, 88, 22)])

    # ---- chimney behind the gable block (its foot hidden by the gable)
    def chimney(x0, x1, top, bot, rmask=None):
        if rmask is not None:
            tint(ic, ic.poly_mask([(x1, top + 30), (x1 + 56, top + 70), (x1 + 66, bot + 30), (x1, bot)]), rmask,
                 (0, 0, 0), 0.4, 12)
        cm = ic.mask("rectangle", (x0, top, x1, bot))
        stones(ic, (x0, top, x1, bot), "#c2aa86", "#7e6a50", course=26)
        tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, top, x1 + 20, bot)), cm, (0, 0, 0), 0.3, 12)
        tint(ic, ic.mask("rectangle", (x0, top, x1, top + 40)), cm, (20, 14, 10), 0.4, 12)  # soot
        ic.outline([(x0, top), (x1, top), (x1, bot), (x0, bot)], 4)
        ic.poly([(x0 - 10, top - 20), (x1 + 10, top - 20), (x1 + 10, top + 2), (x0 - 10, top + 2)], "#d0bc9a",
                "#8e7a5e", edge=4)
        ic.ellipse((x0 + 8, top - 28, x1 - 8, top - 16), "#1c1410", "#0c0806", edge=0)

    chimney(230, 290, 104, 330)

    # ---- wing roof: slate, the left end runs in under the gable block
    roof = [(300, WEAVE + 12), (936, WEAVE + 12), (888, WRIDGE), (640, WRIDGE + 6), (262, WRIDGE)]
    rmask = shingles(ic, roof, SLATE[0], SLATE[1], course=28, stagger=38)
    for _ in range(16):
        x, y = ic.random.uniform(340, 920), ic.random.uniform(WRIDGE, WEAVE)
        r = ic.random.uniform(24, 60)
        col = ic.random.choice([(0, 0, 0), (255, 236, 210), (90, 96, 60), (120, 90, 70)])
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), rmask, col,
             ic.random.uniform(0.08, 0.18), 14)
    tint(ic, ic.poly_mask([(700, WRIDGE), (960, WRIDGE), (960, WEAVE + 14), (760, WEAVE + 14)]), rmask, (0, 0, 0),
         0.2, 50)
    ridge = [(262, WRIDGE - 12), (640, WRIDGE - 6), (890, WRIDGE - 12), (890, WRIDGE + 6), (640, WRIDGE + 12),
             (262, WRIDGE + 6)]
    ic.poly(ridge, "#6e6a6a", "#48464a", edge=4)
    chimney(440, 506, 168, WRIDGE + 34, rmask)
    chimney(784, 836, 196, WRIDGE + 26, rmask)

    # ---- wing, upper storey
    upper = ic.mask("rectangle", (WX0, WEAVE, WX1, BAND))
    stones(ic, (WX0, WEAVE, WX1, BAND), STONE[0], STONE[1], course=40, lit=50, shadow=100)
    for cx in (434, 619, 792):
        ic.window(cx - 26, 494, cx + 26, 560)
        ic.rect((cx - 44, 480, cx + 44, 492), DRESSED[0], DRESSED[1], edge=3)  # drip moulding
        tint(ic, ic.mask("rectangle", (cx - 40, 492, cx + 40, 510)), None, (0, 0, 0), 0.3, 5)
    tint(ic, ic.mask("rectangle", (WX0, WEAVE, WX1, WEAVE + 50)), upper, (0, 0, 0), 0.45, 10)  # eave shadow
    tint(ic, ic.mask("rectangle", (WX1 - 90, WEAVE, WX1 + 40, BAND)), upper, (0, 0, 0), 0.16, 30)

    # ---- wing, ground floor: open serving arcade
    lower = ic.mask("rectangle", (WX0, BAND, WX1, BASE))
    stones(ic, (WX0, BAND, WX1, BASE), STONE[0], STONE[1], course=42, lit=50, shadow=100)
    quoins(ic, WX1, WEAVE, CT, -1)
    tint(ic, ic.mask("rectangle", (WX0, BASE - 80, WX1, BASE)), lower, (44, 46, 22), 0.2, 24)
    tint(ic, ic.mask("rectangle", (WX1 - 90, BAND, WX1 + 40, BASE)), lower, (0, 0, 0), 0.16, 30)
    p = 24
    for ax0, ax1 in ARCHES:
        aw = ax1 - ax0
        acx, cy = (ax0 + ax1) / 2, ATOP + aw / 2
        opening = union(ic.mask("ellipse", (ax0, ATOP, ax1, ATOP + aw)), ic.mask("rectangle", (ax0, cy, ax1, BASE)))
        ring = union(ic.mask("ellipse", (ax0 - p, ATOP - p, ax1 + p, ATOP + aw + p)),
                     ic.mask("rectangle", (ax0 - p, cy, ax1 + p, BASE)))
        ic.fill(ring, DRESSED[0], DRESSED[1], (ATOP - p, BASE), noise=0.14)

        def joints(d, acx=acx, cy=cy, aw=aw, ax0=ax0, ax1=ax1):
            r0, r1 = aw / 2, aw / 2 + p
            for a in np.linspace(math.pi, 2 * math.pi, 8)[1:-1]:
                c, s = math.cos(a), math.sin(a)
                d.line([(acx + c * r0, cy + s * r0), (acx + c * r1, cy + s * r1)], fill=(60, 44, 30, 150), width=4)
            for y in np.arange(cy + 40, BASE, 44):
                for x0, x1 in ((ax0 - p, ax0), (ax1, ax1 + p)):
                    d.line([(x0, y), (x1, y)], fill=(60, 44, 30, 140), width=4)
                    d.line([(x0, y + 4), (x1, y + 4)], fill=(255, 245, 225, 55), width=3)

        ic.overlay(joints, ring)
        ic.poly([(acx - 14, ATOP - p - 6), (acx + 14, ATOP - p - 6), (acx + 10, ATOP + 6), (acx - 10, ATOP + 6)],
                "#e2d2b0", "#a89470", edge=3)  # keystone
        with ic.clipped(opening):
            ic.fill(opening, "#2a1a12", "#0e0804", (ATOP, CT), noise=0.12)
            tint(ic, ic.mask("rectangle", (ax0, ATOP, ax1, ATOP + 70)), None, (0, 0, 0), 0.5, 20)
            tint(ic, ic.mask("ellipse", (acx - 100, CT - 70, acx + 100, CT + 70)), None, (255, 124, 40), 0.42, 26)
            ic.line([(ax0, 694), (ax1, 694)], 6, (70, 50, 32))  # utensil rail at the back
            for hx, ln in ((ax0 + 24, 44), (ax1 - 30, 36)):
                ic.line([(hx, 694), (hx, 694 + ln)], 4, (60, 56, 52))
                ic.draw.ellipse((hx - 9, 694 + ln - 4, hx + 9, 694 + ln + 10), fill=(58, 52, 48, 255))
        ic.overlay(lambda d, b=(ax0 - p, ATOP - p, ax1 + p, ATOP + aw + p): d.arc(b, 180, 360, fill=(50, 36, 24, 190),
                                                                                    width=5))
    tint(ic, ic.mask("rectangle", (WX0, BAND, WX0 + 60, BASE)), lower, (0, 0, 0), 0.3, 18)  # gable block's shadow

    # ---- string course over the whole front
    ic.rect((GX0 - 10, BAND - 12, WX1 + 10, BAND + 8), DRESSED[0], DRESSED[1], edge=4)
    tint(ic, ic.mask("rectangle", (GX0, BAND + 8, WX1, BAND + 36)), None, (0, 0, 0), 0.35, 8)

    # ---- serving counter: oak board on a masonry front
    front = ic.mask("rectangle", (WX0 + 2, CT + 16, WX1 - 2, BASE))
    stones(ic, (WX0 + 2, CT + 16, WX1 - 2, BASE), "#b89c78", "#7a6448", course=28, moss=0.0)
    tint(ic, ic.mask("rectangle", (WX0, CT + 16, WX1, CT + 44)), front, (0, 0, 0), 0.45, 8)
    top = [(WX0 - 6, CT - 8), (WX1 + 6, CT - 8), (WX1 + 10, CT + 18), (WX0 - 10, CT + 18)]
    ic.poly(top, "#b0845a", "#6a4a2c", edge=4)
    ic.line([(WX0, CT + 4), (WX1, CT + 6)], 3, (70, 46, 26, 120))
    ic.outline([(WX0 + 2, CT + 16), (WX1 - 2, CT + 16), (WX1 - 2, BASE), (WX0 + 2, BASE)], 4)

    # ---- on the counter: copper pots, bowls and loaves
    pots = ((430, 132, 92, False), (626, 108, 112, True), (806, 136, 76, False))
    for cx, w, h, _ in pots:
        tint(ic, ic.mask("ellipse", (cx - w * 0.5, CT - 12, cx + w * 0.75, CT + 14)), None, (0, 0, 0), 0.4, 6)
    copper_pot(ic, 430, CT, 132, 92)
    copper_pot(ic, 626, CT, 108, 112, lid=True, body=("#e09a62", "#461a0c"))
    copper_pot(ic, 806, CT, 136, 76, stew=("#c8964a", "#6a4418"))
    steam(ic, [([(412, CT - 96), (398, 680), (420, 640), (404, 602)], 18),
               ([(452, CT - 96), (466, 676), (450, 640)], 13),
               ([(790, CT - 80), (774, 686), (796, 648), (782, 612)], 18),
               ([(830, CT - 80), (842, 700), (828, 666)], 12),
               ([(640, CT - 146), (652, 626), (638, 596)], 10)], 0.55)
    for bx, by in ((528, CT), (528, CT - 12), (528, CT - 24)):
        bowl(ic, bx, by, 52, 18)
    loaf(ic, 706, CT - 2, 50, 30)
    loaf(ic, 882, CT - 2, 38, 24)

    # ---- gabled entrance block
    gwall = ic.poly_mask([(GX0, BASE), (GX0, GEAVE - 4), (GCX, GAPEX + 44), (GX1, GEAVE - 4), (GX1, BASE)])
    stones(ic, (GX0, GAPEX, GX1, BASE), STONE[0], STONE[1], course=40, clip=gwall, lit=50, shadow=100)
    quoins(ic, GX0, GEAVE - 6, BASE, 1)
    quoins(ic, GX1, GEAVE - 6, BASE, -1)
    tint(ic, ic.mask("rectangle", (GX0, BASE - 80, GX1, BASE)), gwall, (44, 46, 22), 0.2, 24)
    tint(ic, ic.mask("rectangle", (GX1 - 70, GAPEX, GX1 + 20, BASE)), gwall, (0, 0, 0), 0.18, 24)
    # oculus in the gable
    ic.ellipse((GCX - 42, 282, GCX + 42, 366), DRESSED[0], DRESSED[1], edge=4)
    ic.ellipse((GCX - 26, 298, GCX + 26, 350), "#3a3638", "#141213", edge=3)
    ic.line([(GCX, 298), (GCX, 350)], 6, (92, 64, 40))
    ic.line([(GCX - 26, 324), (GCX + 26, 324)], 6, (92, 64, 40))
    # upper windows
    for x0 in (104, 236):
        ic.window(x0, 474, x0 + 48, 548)
        ic.rect((x0 - 18, 460, x0 + 66, 472), DRESSED[0], DRESSED[1], edge=3)
    # verges: tile ends along both slopes, a bargeboard shadow on the gable below
    vl = [(26, GEAVE + 4), (GCX, GAPEX), (GCX, GAPEX + 50), (58, GEAVE + 4)]
    vr = [(GCX, GAPEX), (364, GEAVE + 4), (332, GEAVE + 4), (GCX, GAPEX + 50)]
    shadow = ic.poly_mask([(58, GEAVE + 4), (GCX, GAPEX + 50), (332, GEAVE + 4), (332, GEAVE + 40),
                           (GCX, GAPEX + 92), (58, GEAVE + 40)])
    tint(ic, shadow, gwall, (0, 0, 0), 0.45, 10)
    ic.fill(ic.poly_mask(vl), "#8a8888", "#555458", (GAPEX, GEAVE), noise=0.16)
    ic.fill(ic.poly_mask(vr), "#6a6868", "#38363a", (GAPEX, GEAVE), noise=0.16)

    def tile_ends(d):
        for t in np.linspace(0.04, 0.96, 12):
            for (xa, ya), (xb, yb) in (((58, GEAVE + 4), (GCX, GAPEX + 50)), ((332, GEAVE + 4), (GCX, GAPEX + 50))):
                x, y = xa + (xb - xa) * t, ya + (yb - ya) * t
                d.line([(x, y - 30), (x, y - 4)], fill=(30, 26, 26, 110), width=4)
                d.line([(x + 5, y - 30), (x + 5, y - 6)], fill=(230, 226, 220, 50), width=3)

    ic.overlay(tile_ends, union(ic.poly_mask(vl), ic.poly_mask(vr)))
    ic.outline(vl, 5)
    ic.outline(vr, 5)
    ic.outline([(GX0, GEAVE), (GX0, BASE), (GX1, BASE), (GX1, GEAVE)], 5)
    # arched entrance with a dressed surround
    ic.door(148, 692, 242, BASE, arched=True, surround=DRESSED[0])
    tint(ic, ic.mask("rectangle", (148, 692, 242, 760)), None, (0, 0, 0), 0.3, 12)

    # ---- plinth
    stones(ic, (GX0 - 8, BASE - 14, WX1 + 8, BASE + 12), "#9a8468", "#665440", course=26, moss=0.0)
    ic.outline([(GX0 - 8, BASE - 14), (WX1 + 8, BASE - 14), (WX1 + 8, BASE + 12), (GX0 - 8, BASE + 12)], 4)

    # ---- trestle table and bench in front of the gable block
    tint(ic, ic.mask("rectangle", (60, 826, 320, 900)), None, (0, 0, 0), 0.35, 16)  # table's shadow on the wall
    tint(ic, ic.mask("ellipse", (20, 900, 300, 960)), None, (0, 0, 0), 0.3, 12)
    for x in (70, 236):
        ic.beam((x - 20, 930), (x, 834), 14, (96, 66, 40))
        ic.beam((x + 20, 930), (x, 834), 14, (84, 56, 34))
    tt = [(24, 812), (286, 812), (292, 834), (18, 834)]
    ic.poly(tt, "#bc9064", "#86603c", edge=4)
    ic.rect((18, 834, 292, 852), "#7a5434", "#5a3c22", edge=4)
    tint(ic, ic.mask("rectangle", (20, 852, 290, 880)), None, (0, 0, 0), 0.35, 8)
    jug(ic, 62, 814, 46, 70)
    bowl(ic, 128, 814, 50, 18)
    bowl(ic, 250, 814, 46, 16)
    loaf(ic, 190, 812, 52, 30)
    # bench
    for x in (60, 250):
        ic.beam((x, 912), (x - 6, 960), 14, (84, 56, 34))
    ic.poly([(14, 890), (298, 890), (302, 904), (10, 904)], "#b08660", "#7a5636", edge=4)
    ic.rect((10, 904, 302, 918), "#6e4a2e", "#4e341e", edge=4)

    # ---- props bottom right: grain sacks and a basket of loaves
    tint(ic, ic.mask("ellipse", (820, 930, 1020, 990)), None, (0, 0, 0), 0.3, 12)
    grain_sack(ic, 900, 952, 104, 138, col=("#c2a676", "#5a462c"))
    grain_sack(ic, 966, 974, 100, 112, open_top=True, col=("#d2bc8c", "#665234"))
    ic.basket(826, 916, 918, 980)
    loaf(ic, 848, 918, 44, 26)
    loaf(ic, 892, 916, 40, 24)
    loaf(ic, 870, 904, 40, 22)
