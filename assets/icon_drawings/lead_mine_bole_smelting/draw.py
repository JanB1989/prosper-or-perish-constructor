"""Bole Lead Mine (lead_mine_bole_smelting): an open, wind-blown hilltop bole hearth beside the galena rake.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/lead_mine_bole_smelting/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/lead_mine_bole_smelting

Identity: a low three-sided dry-stone bole hearth on a grassy crest, open to the wind on the left,
its fire of wood and dressed galena blazing and the smoke streaming away to the right. The pale
limestone rake with its braced gash on the left and the heap of cubic galena bottom right carry
the family over from the Lead Mine; a stack of cordwood and freshly cast lead pigs show the new
smelting step.

Local helpers (not in the kit): ``union``, ``tint``, ``cube``, ``cube_heap``, ``limestone`` (shared
with the family), ``stones``, ``smoke``, ``flame``, ``log_end`` (from cookshop), ``pig`` (lead pig).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 23
REFS = ("charcoal_maker", "bog_iron_smelter", "local_smelters", "clay_pit")

GAL = (92, 100, 116)  # galena front face
GAL_LIT = (168, 178, 196)  # galena top face, metallic sheen
GAL_DARK = (30, 34, 42)
LIME = "#d0c2a4"
LIME_DARK = "#7a6c58"
TURF = ("#7e8440", "#434a22")
TIMBER = (116, 78, 48)
IRON = (40, 40, 44)
DARK = (28, 20, 14)


# ---------------------------------------------------------------- helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def _mix(a, b, t):
    return tuple(int(x * (1 - t) + y * t) for x, y in zip(a, b))


def cube(ic: Icon, cx: float, cy: float, s: float, deg: float = 0.0, k: float = 1.0) -> None:
    """One cubic galena lump seen from the raised front camera: bright top face, lead-grey front,
    dark right side, a sheen line on the lit edges. ``k`` scales the tone."""
    h = s / 2
    kx, ky = h * 0.42, h * 0.62
    j = lambda: ic.random.uniform(-0.07, 0.07) * s  # noqa: E731
    f = [(-h + j(), -h + j()), (h + j(), -h + j()), (h + j(), h + j()), (-h + j(), h + j())]
    top = [f[0], f[1], (f[1][0] + kx, f[1][1] - ky), (f[0][0] + kx, f[0][1] - ky)]
    side = [f[1], top[2], (f[2][0] + kx, f[2][1] - ky), f[2]]
    rot = lambda p: ic.rotate(p, (cx, cy), deg)  # noqa: E731
    f, top, side = rot(f), rot(top), rot(side)
    sc = lambda c: tuple(int(min(255, v * k)) for v in c)  # noqa: E731
    ys = [p[1] for p in top + f]
    ic.fill(ic.poly_mask(top), sc(GAL_LIT), sc(_mix(GAL_LIT, GAL, 0.5)), (min(ys), max(ys)), noise=0.1)
    ic.fill(ic.poly_mask(f), sc(GAL), sc(_mix(GAL, GAL_DARK, 0.55)), (f[0][1], f[3][1]), noise=0.14)
    ic.fill(ic.poly_mask(side), sc(_mix(GAL, GAL_DARK, 0.65)), sc(GAL_DARK), (side[1][1], side[3][1]), noise=0.12)
    if ic.random.random() < 0.5:  # cleavage step on the front face
        y = ic.random.uniform(0.25, 0.7)
        a = (f[0][0] + (f[3][0] - f[0][0]) * y, f[0][1] + (f[3][1] - f[0][1]) * y)
        b = (f[1][0] + (f[2][0] - f[1][0]) * y, f[1][1] + (f[2][1] - f[1][1]) * y)
        ic.line([a, b], 3, (24, 28, 36, 140))
    ic.line([f[3], f[0], f[1]], 3, (220, 230, 245, 120))
    hull = [f[0], top[3], top[2], side[2], f[2], f[3]]
    ic.outline(hull, 4, (22, 24, 30, 200))


def cube_heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float, rows: int) -> None:
    """Mound of cubic galena: dark body, then rows of cubes laid back to front."""
    cx = (x0 + x1) / 2
    body = [(x0, base), (x0 + (cx - x0) * 0.35, base - (base - top) * 0.62), (cx - r * 1.2, top + r * 0.2),
            (cx + r * 0.9, top + r * 0.15), (x1 - (x1 - cx) * 0.3, base - (base - top) * 0.58), (x1, base)]
    ic.poly(body, (66, 72, 84), (22, 24, 30), noise=0.3)
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.55 + (base - top - r * 1.0) * t
        half = (x1 - x0) / 2 * (0.3 + 0.66 * t)
        n = max(1, int(2 * half / (r * 1.2)))
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + ic.random.uniform(-10, 10)
            cube(ic, x, y + ic.random.uniform(-6, 6), r * ic.random.uniform(0.75, 1.1), ic.random.uniform(-24, 24),
                 ic.random.uniform(0.8, 1.08))


def limestone(ic: Icon, pts, beds, turf: float = 34) -> Image.Image:
    """Pale bedded limestone mass: lit top-left, projecting ledges (lit lip, shadow below), sparse
    irregular joints, weathering blotches, dark grimy foot and a turf cap. Returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, LIME, LIME_DARK, radial=(min(xs) + 60, min(ys) - 40, (max(xs) - min(xs)) * 1.05), noise=0.24)
    for _ in range(18):  # weathering: grey, ochre and dark blotches
        x, y = ic.random.uniform(min(xs), max(xs)), ic.random.uniform(min(ys), max(ys))
        r = ic.random.uniform(30, 80)
        col = ic.random.choice([(0, 0, 0), (0, 0, 0), (180, 150, 90), (255, 248, 230), (90, 96, 60)])
        tint(ic, ic.mask("ellipse", (x - r * 1.5, y - r * 0.7, x + r * 1.5, y + r * 0.7)), m, col,
             ic.random.uniform(0.08, 0.2), 16)
    # beds split by joints into big weathered blocks, each shaded as a form (clints and grikes)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    d, sd = ImageDraw.Draw(lay), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    edges = [min(ys) - 40] + list(beds) + [max(ys) + 20]
    for y0, y1 in zip(edges[:-1], edges[1:]):
        x = min(xs) - rnd(0, 120)
        while x < max(xs):
            w = rnd(170, 380)
            j = lambda k=12: rnd(-k, k)  # noqa: E731
            q = [(x + 6 + j(), y0 + 6 + j(4)), (x + w * 0.5, y0 + 6 + j(8)), (x + w - 8 + j(), y0 + 10 + j(6)),
                 (x + w - 8 + j(16), (y0 + y1) / 2), (x + w - 12 + j(), y1 - 8), (x + 10 + j(), y1 - 8 + j(4))]
            t = rnd(-1, 1)
            d.polygon(q, fill=(24, 16, 10, int(-t * 50)) if t < 0 else (255, 244, 220, int(t * 40)))
            d.line([q[0], q[1], q[2]], fill=(255, 246, 228, 110), width=7)  # lit lip of the ledge
            d.line([q[2], q[3], q[4]], fill=(34, 26, 18, 140), width=6)  # joint on the shadow side
            sd.polygon([(x + w - 8, y0 + 14), (x + w + 26, y0 + 34), (x + w + 26, y1), (x + w - 8, y1)], fill=255)
            sd.line([(x, y1 + 10), (x + w, y1 + 10)], fill=255, width=20)  # ledge shadow on the bed below
            x += w
    tint(ic, shadow, m, (20, 14, 10), 0.32, 8)
    grikes = Image.new("L", (ic.size, ic.size), 0)
    gd = ImageDraw.Draw(grikes)
    for y in beds:
        gd.line([(x, y + rnd(-12, 12)) for x in range(-40, ic.size + 80, 50)], fill=255, width=7)
    tint(ic, grikes, m, (30, 24, 18), 0.75)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, ic.mask("rectangle", (max(xs) - 220, 0, ic.size, ic.size)), m, (10, 8, 6), 0.2, 60)
    tint(ic, ic.mask("rectangle", (0, max(ys) - 140, ic.size, ic.size)), m, (46, 44, 26), 0.35, 40)
    # turf cap along the top edge
    top_edge = [p for p in pts if p[1] < max(ys) - 80]
    cap = Image.new("L", (ic.size, ic.size), 0)
    cd = ImageDraw.Draw(cap)
    cd.line(top_edge, fill=255, width=int(turf * 2), joint="curve")
    for p in top_edge[1:-1:2]:  # tufts hanging over the ledge
        cd.ellipse((p[0] - 22, p[1] - 10, p[0] + 22, p[1] + turf * 0.7 + ic.random.uniform(0, 22)), fill=255)
    cap = ic.intersect(cap, m)
    ic.fill(cap, TURF[0], TURF[1], (min(ys), min(ys) + turf * 4), noise=0.4)
    tint(ic, ImageChops.subtract(cap.filter(ImageFilter.MaxFilter(13)), cap), m, (0, 0, 0), 0.5, 4)
    ic.outline(pts)
    return m


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/dry-stone wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines (from cookshop)."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.7, 1.1)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.1, 2.6)
            j = lambda: rnd(-5, 5)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 60)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=6)
            x += w
        y += h
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def smoke(ic: Icon, puffs, light=("#e4e0d8", "#8a8680")) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath (from cookshop)."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.8 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, light[0], light[1], radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#ffbe55", "#c9451c"), inner=("#fff3c4", "#ffb449")) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one (from cookshop)."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (inner, 0.5, 0.62)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def lick(ic: Icon, cx: float, base: float, w: float, h: float, lean: float, phase: float = 0.0,
         clip: Image.Image | None = None) -> None:
    """One wind-bent lick of flame: soft dim orange-red fringe, orange body, yellow-white core low
    down by the fuel. The centreline bends right (``lean``) and sways a little (``phase``)."""
    ts = np.linspace(0, 1, 48)
    prof = (1 - ts) ** 0.8 * (0.7 + 0.3 * np.sin(np.pi * np.clip(ts * 2.2, 0, 1)))

    def tongue(kw: float, kh: float, blur: float) -> Image.Image:
        t = ts
        c = cx + lean * kh * t ** 1.6 + w * 0.16 * kh * t * np.sin(2 * np.pi * 1.2 * t + phase)
        y = base - h * kh * t
        half = w / 2 * kw * prof
        pts = [(c[i] - half[i] * 1.08, y[i]) for i in range(len(t))]  # windward side a touch fuller
        pts += [(c[i] + half[i] * 0.92, y[i]) for i in range(len(t))][::-1]
        m = ic.poly_mask(pts)
        if blur:
            m = m.filter(ImageFilter.GaussianBlur(blur))
        return ic.intersect(m, clip) if clip is not None else m

    ic.fill(tongue(1.0, 1.0, 4), "#c8521e", "#7c2814", (base, base - h), noise=0.1, chroma=0.03)
    ic.fill(tongue(0.74, 0.84, 2), "#f8a444", "#dc6a2a", (base, base - h * 0.84), noise=0.08, chroma=0.03)
    ic.fill(tongue(0.44, 0.44, 3), "#fff6dc", "#ffd07a", (base, base - h * 0.44), noise=0.05, chroma=0.02)


def pebble(ic: Icon, cx: float, cy: float, r: float, base=(170, 160, 138), dark=(96, 88, 74)) -> None:
    """Small loose limestone block lying in the turf: lit top, dark foot, soft edge, contact shadow."""
    ic.shade(ic.mask("ellipse", (cx - r * 1.3, cy + r * 0.1, cx + r * 1.5, cy + r * 0.9)), (20, 22, 10), 0.4, 4)
    pts = ic.jitter(cx, cy, r * 1.2, r * 0.8, 7, 0.22)
    ic.fill(ic.poly_mask(pts), base, dark, radial=(cx - r * 0.6, cy - r * 0.7, r * 2.2), noise=0.2)
    ic.outline(pts, 3, (40, 32, 24, 170))


def tufts(ic: Icon, x: float, y: float, s: float, n: int = 5) -> None:
    """Clump of grass blades breaking a hard edge: dark olive blades with lighter lit tips."""
    for _ in range(n):
        bx = x + ic.random.uniform(-s, s)
        ln = s * ic.random.uniform(0.8, 1.5)
        a = math.radians(ic.random.uniform(-35, 25))
        tip = (bx + math.sin(a) * ln, y - math.cos(a) * ln)
        blade = [(bx - s * 0.13, y), tip, (bx + s * 0.13, y)]
        ic.fill(ic.poly_mask(blade), (138, 138, 70), (54, 60, 28), (tip[1], y), noise=0.2)


def log_end(ic: Icon, cx, cy, r) -> None:
    """Sawn log end: bark ring, pale end grain lit from the upper left (from cookshop)."""
    ic.fill(ic.mask("ellipse", (cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5)), "#6a4a30", "#2e1e12", (cy - r, cy + r))
    k = ic.random.uniform(0.78, 1.05)
    lite, dark = tuple(int(v * k) for v in (216, 178, 124)), tuple(int(v * k) for v in (138, 94, 50))
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), lite, dark,
            radial=(cx - r * 0.4, cy - r * 0.5, r * 2.0), noise=0.14)
    if ic.random.random() < 0.35:
        ic.shade(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), (120, 116, 108), 0.35)
    ic.overlay(lambda d: d.arc((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), 200, 470,
                               fill=(120, 80, 40, 70), width=2))


def pig(ic: Icon, x0: float, y0: float, ln: float, h: float, deg: float = 0.0) -> None:
    """Cast lead pig lying on the ground: dull bluish-grey bar, lit top face, rounded ends."""
    d = h * 0.55
    front = [(0, 0), (ln, 0), (ln - h * 0.18, h), (h * 0.18, h)]
    top = [(0, 0), (ln, 0), (ln - d * 0.35, -d), (d * 0.45, -d)]
    fr = ic.rotate(front, (x0, y0), deg)
    tp = ic.rotate(top, (x0, y0), deg)
    ic.fill(ic.poly_mask(tp), (150, 158, 172), (104, 110, 122), (min(p[1] for p in tp), max(p[1] for p in tp)), noise=0.08)
    ic.fill(ic.poly_mask(fr), (112, 118, 128), (58, 62, 70), (x0, x0 + ln), vertical=False, noise=0.1)
    ic.line([fr[0], fr[1]], 3, (228, 234, 242, 150))
    ic.outline(fr[:2] + [fr[2], fr[3]], 4, (26, 28, 34, 200))
    ic.outline([tp[0], tp[3], tp[2], tp[1]], 4, (26, 28, 34, 160))




# ---------------------------------------------------------------- drawing
def lip(ic: Icon, pts, lit=(238, 226, 200, 120), dark=(26, 20, 14, 110)) -> None:
    """Lit top edge and shadowed underside on each level run of a ragged dry-stone top."""
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        if abs(y1 - y0) < 9 and x1 - x0 > 20:
            ic.line([(x0 + 4, y0 + 5), (x1 - 4, y1 + 5)], 5, lit)
            ic.line([(x0 + 8, y0 + 16), (x1 - 2, y1 + 16)], 4, dark)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.88
    BX0, BX1 = 470, 850  # bole back wall
    rnd = ic.random.uniform

    # ---- fume streaming right with the wind from the fire, behind the walls
    smoke(ic, [(992, 300, 40), (936, 300, 54), (866, 318, 66), (790, 346, 74), (716, 390, 72), (656, 440, 62),
               (608, 494, 50), (576, 540, 40)], ("#e6e2d6", "#8c8880"))

    # ---- grassy upland crest: a lit swell in the middle, falling away darker to the right and front
    hill = [(10, 912), (14, 720), (120, 660), (280, 610), (440, 586), (600, 574), (740, 582), (860, 608),
            (950, 648), (1004, 700), (1016, 744), (1016, 912)]
    hm = ic.poly_mask(hill)
    ic.fill(hm, "#8c8a4c", "#4a4828", radial=(360, 540, 760), noise=0.34)
    tint(ic, ic.mask("ellipse", (500, 590, 900, 790)), hm, (214, 206, 128), 0.22, 50)  # sunlit swell
    tint(ic, ic.mask("rectangle", (0, 850, ic.size, 980)), hm, (30, 34, 14), 0.32, 40)  # foreground in shade
    tint(ic, ic.mask("ellipse", (880, 600, 1160, 980)), hm, (26, 30, 12), 0.38, 50)  # far flank turned away
    tint(ic, ic.mask("rectangle", (356, 600, 452, 912)), hm, (36, 42, 18), 0.42, 22)  # darker fringe at crag foot
    for _ in range(70):  # tussocks and bare patches
        x, y = rnd(20, 1010), rnd(610, 900)
        r = rnd(14, 30)
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y - r * 0.6, x + r * 1.6, y + r * 0.4)), hm,
             ic.random.choice([(186, 180, 100), (40, 44, 20), (120, 90, 50)]), rnd(0.12, 0.28), 6)
    ic.outline(hill)

    # ---- limestone rake on the left (the mine), with the braced gash
    crag = [(18, 905), (22, 640), (40, 600), (52, 520), (92, 500), (104, 440), (150, 420), (176, 376),
            (240, 372), (268, 398), (300, 404), (318, 470), (352, 520), (360, 600), (380, 660), (388, 905)]
    rock = limestone(ic, crag, (500, 610, 740), turf=26)
    gash = [(150, 400), (200, 386), (216, 500), (206, 650), (192, 750), (170, 660), (158, 520)]
    with ic.clipped(rock):
        lining = ic.poly_mask(gash).filter(ImageFilter.MaxFilter(37))
        ic.fill(lining, (112, 122, 140), (38, 42, 52), (380, 800), noise=0.4)
        for _ in range(24):
            x, y = rnd(120, 250), rnd(380, 780)
            if lining.getpixel((int(x), int(y))):
                s = rnd(7, 12)
                ic.shade(ic.poly_mask([(x - s, y), (x, y - s), (x + s, y), (x, y + s)]), (215, 226, 242), 0.7)
        ic.poly(gash, "#1a1816", "#07070a", edge=0, noise=0.1)
        for y, w in ((460, 60), (580, 66), (690, 50)):
            cx = 186 - (y - 460) * 0.03
            ic.beam((cx - w / 2 - 12, y - 6), (cx + w / 2 + 12, y + 6), 16, TIMBER)
    ic.outline(gash, 4)
    # rock foot sinks into the turf: grass creeping up the base, scree and tussocks over the seam
    tint(ic, ic.mask("rectangle", (290, 640, 420, 912)), rock, (74, 84, 38), 0.4, 26)
    for wedge in ([(296, 912), (330, 890), (360, 858), (386, 842), (408, 862), (436, 912)],
                  [(352, 716), (366, 690), (384, 668), (402, 684), (420, 716)]):
        wm = ic.poly_mask(wedge)
        ic.fill(wm, "#86844a", "#4c4a28", (min(p[1] for p in wedge), 912), noise=0.34)  # turf lapping the foot
        tint(ic, ImageChops.subtract(wm.filter(ImageFilter.MaxFilter(15)), wm), rock, (20, 24, 10), 0.45, 5)
    for x, y, r in ((398, 676, 13), (424, 692, 9), (446, 680, 7), (370, 872, 15), (404, 888, 11), (386, 900, 9),
                    (434, 896, 8), (456, 874, 7)):
        pebble(ic, x, y, r)
    for x, y, s in ((384, 702, 16), (414, 704, 11), (388, 862, 17), (378, 908, 15), (420, 906, 12), (352, 890, 12)):
        tufts(ic, x, y, s, 6)

    # ---- the bole: a low three-sided dry-stone windbreak, sooted, open to the wind on the left
    top = [(BX0 + 2, 598), (BX0 + 26, 594), (BX0 + 30, 576), (BX0 + 92, 570), (BX0 + 96, 556), (BX0 + 170, 552),
           (BX0 + 176, 532), (BX0 + 232, 528), (BX0 + 238, 546), (BX0 + 300, 550), (BX0 + 306, 540),
           (BX1 - 44, 544), (BX1 - 40, 556), (BX1, 560)]
    top = [(x, y + rnd(-3, 3)) for x, y in top]
    back = [(BX0, 700)] + top + [(BX1, 700)]
    bm = ic.poly_mask(back)
    stones(ic, (BX0, 520, BX1, 700), "#908270", "#5a4e40", course=33, clip=bm)
    lip(ic, top)
    tint(ic, ic.mask("ellipse", (BX0 + 60, 510, BX1 + 40, 670)), bm, (20, 14, 10), 0.5, 30)  # soot
    ic.outline(back, 5)
    # hearth floor, glow and the fire of wood and dressed ore
    floor = ic.mask("ellipse", (BX0 - 16, 666, BX1 - 40, 772)).filter(ImageFilter.GaussianBlur(3))
    ic.fill(floor, "#3a2a1e", "#1a120c", (660, 770), noise=0.2)
    tint(ic, ic.mask("ellipse", (BX0 - 30, 590, BX0 + 330, 800)), union(bm, floor), (255, 116, 36), 0.45, 50)
    # rolling fume at the fire, feeding the plume
    wisp = Image.new("L", (ic.size, ic.size), 0)
    ImageDraw.Draw(wisp).line([(BX0 + 150, 700), (BX0 + 160, 640), (BX0 + 128, 590), (BX0 + 106, 540)], fill=255,
                              width=64, joint="curve")
    tint(ic, wisp, bm, (150, 144, 136), 0.5, 22)  # fume rising off the fire against the sooted wall
    # licks of flame, all bent right by the wind
    bed = ic.mask("ellipse", (BX0 + 10, 694, BX0 + 296, 748)).filter(ImageFilter.GaussianBlur(8))
    ic.fill(bed, "#e2702c", "#9a3416", (694, 748), noise=0.08, chroma=0.03)  # burning bed the licks rise from
    for fx, fw, fh, ln, ph in ((58, 96, 108, 40, 0.4), (136, 128, 152, 64, 2.1), (210, 90, 96, 38, 4.0),
                               (258, 58, 58, 22, 1.2)):
        lick(ic, BX0 + fx, 734, fw, fh, ln, ph)
    core = ic.mask("ellipse", (BX0 + 40, 704, BX0 + 260, 744)).filter(ImageFilter.GaussianBlur(10))
    ic.fill(core, "#fff4d4", "#ffc86c", (704, 744), noise=0.05, chroma=0.02)  # white heat down by the fuel
    for x, y, r in ((BX0 + 40, 722, 28), (BX0 + 96, 732, 32), (BX0 + 160, 726, 30), (BX0 + 218, 734, 28)):
        cube(ic, x, y, r * 1.2, rnd(-20, 20), 0.75)  # galena roasting on the fire
        tint(ic, ic.mask("ellipse", (x - r, y - r, x + r * 0.6, y + r * 0.2)), None, (255, 140, 50), 0.4, 8)
    ic.beam((BX0 - 16, 752), (BX0 + 170, 738), 22, (70, 44, 26))
    ic.beam((BX0 + 120, 746), (BX0 + 280, 756), 20, (60, 38, 22))
    lick(ic, BX0 + 104, 752, 30, 42, 22, 1.0)
    lick(ic, BX0 + 196, 756, 22, 30, 16, 3.0)
    # ember glow bleeding onto the hearth floor and a scatter of coals
    tint(ic, ic.mask("ellipse", (BX0 - 10, 736, BX0 + 310, 790)), floor, (255, 150, 60), 0.35, 24)
    for _ in range(10):
        x, y, r = BX0 + rnd(0, 290), rnd(750, 768), rnd(3, 7)
        tint(ic, ic.mask("ellipse", (x - r * 3, y - r * 2, x + r * 3, y + r * 2)), floor, (255, 140, 50), 0.4, 6)
        ic.draw.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8),
                        fill=ic.random.choice([(255, 214, 128, 255), (255, 170, 80, 255), (214, 92, 40, 255)]))
    # right side wall stepping down towards us, and the low front wall on the right half
    stop = [(BX1 - 38, 562), (BX1 + 8, 554), (BX1 + 12, 586), (BX1 + 42, 590), (BX1 + 46, 628), (BX1 + 74, 634)]
    side = [(BX1 - 34, 780)] + stop + [(BX1 + 76, 796)]
    sm = ic.poly_mask(side)
    stones(ic, (BX1 - 44, 548, BX1 + 80, 800), "#9c8e78", "#5e5244", course=32, clip=sm)
    tint(ic, ic.mask("rectangle", (BX1 + 14, 540, BX1 + 90, 800)), sm, (0, 0, 0), 0.28, 14)
    lip(ic, stop)
    ic.outline(side, 5)
    front = [(BX0 + 290, 796), (BX0 + 294, 710), (BX0 + 340, 694), (BX1 - 34, 700), (BX1 - 30, 800)]
    fm = ic.poly_mask(front)
    stones(ic, (BX0 + 280, 690, BX1, 805), "#a4967e", "#645848", course=30, clip=fm)
    tint(ic, ic.mask("rectangle", (BX0 + 280, 690, BX0 + 350, 805)), fm, (255, 140, 50), 0.4, 16)  # fire light
    ic.outline(front, 5)
    tint(ic, ic.mask("rectangle", (BX0 - 60, 780, BX1 + 90, 830)), hm, (0, 0, 0), 0.35, 16)  # contact shadow

    # ---- cordwood stack left of the bole, in front of the rake; its ends catch the firelight
    stack = [(330, 846), (334, 732), (372, 712), (470, 710), (492, 736), (492, 846)]
    km = ic.poly_mask(stack)
    ic.poly(stack, "#4a3220", "#24160c", edge=0)
    for y, xs in ((826, (352, 392, 432, 470)), (788, (362, 402, 442, 478)), (750, (376, 416, 456))):
        for x in xs:
            log_end(ic, x + rnd(-4, 4), y + rnd(-4, 4), rnd(16, 21))
    tint(ic, ic.mask("rectangle", (310, 700, 368, 850)), km, (0, 0, 0), 0.24, 14)
    tint(ic, ic.mask("ellipse", (400, 680, 640, 870)), km, (255, 130, 50), 0.42, 24)

    # ---- heap of cubic galena, bottom right
    cube_heap(ic, 760, 1016, 986, 780, 42, 4)

    # ---- freshly cast lead pigs resting on the grass in front of the hearth
    tint(ic, ic.mask("ellipse", (480, 870, 790, 948)), hm, (0, 0, 0), 0.34, 14)
    pig(ic, 520, 860, 150, 36, -2)
    pig(ic, 600, 894, 140, 34, 3)
    pig(ic, 500, 902, 120, 32, -1)
