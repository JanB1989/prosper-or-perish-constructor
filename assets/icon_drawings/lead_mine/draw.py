"""Lead Mine (lead_mine): a windlass over a shaft on a bedded limestone outcrop with a galena rake.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/lead_mine/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/lead_mine

Identity: a timber hand windlass (stowce) with its rope and a kibble of ore over a stone-collared
shaft, in front of a pale bedded limestone outcrop capped with upland turf; a worked-out rake vein
cuts down through the rock, braced with stemples and lined with blue-grey galena. A heap of cubic
galena bottom right, a basket of ore and a pick bottom left. Iron mine reads through its adit and
rust; this one through the windlass, the pale limestone and the blue-grey cubes.

Family (lead_mine, lead_mine_bole_smelting, lead_mine_cupola_smelting) shares the galena palette,
the ``cube`` / ``cube_heap`` helpers, the limestone and the timber colours.
Local helpers (not in the kit): ``union``, ``tint``, ``cube``, ``cube_heap``, ``limestone``, ``windlass``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("schwaz_mine", "clay_pit", "stone_quarry", "sand_pit")

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


def windlass(ic: Icon, xl: float, xr: float, top: float, base: float, rope_x: float, kibble_y: float) -> None:
    """Hand windlass over a shaft: stone collar and dark mouth, sole-trees, two posts with braces,
    rope drum with coiled rope, crank handles, a rope and an iron-hooped kibble full of galena."""
    w = xr - xl
    cx = (xl + xr) / 2
    # collar and shaft mouth
    ring = ic.mask("ellipse", (xl - 50, base - 70, xr + 50, base + 34))
    ic.fill(ring, "#b4a48a", "#6a5c4a", (base - 70, base + 34), noise=0.28)
    for a in np.linspace(0, 2 * math.pi, 20, endpoint=False):
        tint(ic, ic.mask("line", [(cx + math.cos(a) * w * 0.38, base - 18 + math.sin(a) * 30),
                                  (cx + math.cos(a) * (w / 2 + 50), base - 18 + math.sin(a) * 52)], width=5),
             ring, (40, 32, 24), 0.55)
    ic.overlay(lambda d: d.ellipse((xl - 50, base - 70, xr + 50, base + 34), outline=(40, 28, 20, 200), width=5))
    ic.fill(ic.mask("ellipse", (xl + 6, base - 50, xr - 6, base + 12)), "#161412", "#050506", (base - 50, base + 12),
            noise=0.05)
    # rope and kibble
    dy = top + 34
    ic.line([(rope_x, dy + 30), (rope_x, kibble_y - 16)], 11, (54, 40, 26))
    ic.line([(rope_x, dy + 30), (rope_x, kibble_y - 16)], 6, (176, 150, 104))
    ic.overlay(lambda d: d.arc((rope_x - 46, kibble_y - 30, rope_x + 46, kibble_y + 26), 190, 350,
                               fill=IRON + (255,), width=8))
    for x, y, s in ((rope_x - 26, kibble_y - 4, 32), (rope_x + 4, kibble_y - 14, 36), (rope_x + 32, kibble_y - 2, 28)):
        cube(ic, x, y, s, ic.random.uniform(-20, 20), 1.05)
    kib = [(rope_x - 50, kibble_y), (rope_x + 50, kibble_y), (rope_x + 40, kibble_y + 86), (rope_x - 40, kibble_y + 86)]
    ic.poly(kib, "#946a44", "#48301c", (rope_x - 50, rope_x + 50), vertical=False, noise=0.22)
    for y in (kibble_y + 16, kibble_y + 64):
        ic.line([(rope_x - 48 + (y - kibble_y) * 0.1, y), (rope_x + 48 - (y - kibble_y) * 0.1, y)], 8, IRON)
    # frame
    ic.beam((xl - 60, base + 10), (xr + 60, base + 10), 28, (94, 64, 40))
    ic.beam((xl - 4, base + 8), (xl + 6, top), 48, TIMBER)
    ic.beam((xr + 4, base + 8), (xr - 6, top), 48, (104, 70, 44))
    ic.beam((xl - 60, base + 4), (xl, base - 140), 18, (92, 62, 38))
    ic.beam((xr + 60, base + 4), (xr, base - 140), 18, (92, 62, 38))
    ic.shade(ic.poly_mask([(xl - 18, top), (xl, top), (xl - 8, base + 8), (xl - 26, base + 8)]), (255, 238, 210), 0.25)
    ic.shade(ic.poly_mask([(xr + 2, top), (xr + 22, top), (xr + 26, base + 8), (xr + 6, base + 8)]), alpha=0.3)
    # rope drum
    drum = [(xl + 6, dy - 30), (xr - 6, dy - 30), (xr - 6, dy + 32), (xl + 6, dy + 32)]
    ic.poly(drum, "#9e7450", "#442c18", noise=0.2, edge=5)
    tint(ic, ic.mask("rectangle", (xl, dy - 30, xr, dy - 14)), ic.poly_mask(drum), (255, 238, 210), 0.35, 4)
    for x in np.arange(xl + 40, xr - 30, 16):  # coiled rope
        ic.line([(x, dy - 24), (x + 10, dy + 26)], 7, (178, 150, 106))
        ic.line([(x + 7, dy - 24), (x + 17, dy + 26)], 3, (64, 48, 30, 200))
    for x in (xl + 6, xr - 6):
        ic.ellipse((x - 24, dy - 28, x + 24, dy + 30), "#8a6242", "#44301c", edge=4)
        ic.ellipse((x - 9, dy - 8, x + 9, dy + 10), "#5c5858", "#282626", edge=3)
    # crank handles: left arm down, right arm up
    for p, q, h0, h1 in (((xl + 6, dy + 1), (xl - 56, dy + 76), (xl - 100, dy + 76), (xl - 50, dy + 76)),
                         ((xr - 6, dy + 1), (xr + 58, dy - 66), (xr + 52, dy - 66), (xr + 104, dy - 66))):
        ic.line([p, q], 20, DARK)
        ic.line([p, q], 11, (88, 86, 92))
        ic.line([h0, h1], 24, DARK)
        ic.line([h0, h1], 15, (136, 98, 62))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95

    # ---- bedded limestone outcrop with a turf cap, stepped and irregular
    crag = [(20, 905), (24, 640), (40, 628), (52, 540), (96, 520), (104, 462), (132, 440), (140, 392),
            (176, 380), (204, 318), (262, 304), (290, 284), (336, 300), (386, 292), (410, 312), (428, 350),
            (500, 352), (522, 372), (560, 396), (620, 400), (646, 428), (700, 446), (722, 500), (768, 516),
            (780, 600), (802, 640), (810, 905)]
    rock = limestone(ic, crag, (430, 530, 640, 760), turf=28)

    # ---- worked-out rake vein: dark gash lined with galena, braced by stemples
    gash = [(178, 368), (238, 336), (256, 480), (244, 660), (224, 770), (198, 680), (184, 520)]
    with ic.clipped(rock):
        lining = ic.poly_mask(gash).filter(ImageFilter.MaxFilter(45))
        ic.fill(lining, (112, 122, 140), (38, 42, 52), (330, 800), noise=0.4)
        for _ in range(16):  # glints of cubic galena in the vein walls
            x, y = ic.random.uniform(150, 290), ic.random.uniform(330, 800)
            if lining.getpixel((int(x), int(y))):
                s = ic.random.uniform(6, 11)
                ic.shade(ic.poly_mask([(x - s, y), (x, y - s), (x + s, y), (x, y + s)]), (205, 216, 232), 0.5)
        ic.poly(gash, "#1a1816", "#07070a", edge=0, noise=0.1)
        for y, w in ((430, 70), (560, 78), (690, 58)):
            cx = 218 - (y - 430) * 0.03
            ic.beam((cx - w / 2 - 12, y - 6), (cx + w / 2 + 12, y + 6), 16, TIMBER)
        tint(ic, ic.mask("rectangle", (256, 330, 336, 820)), None, (0, 0, 0), 0.22, 20)
    ic.outline(gash, 4)

    # ---- spoil apron
    apron = [(12, 968), (56, 896), (300, 880), (720, 880), (880, 896), (1008, 968)]
    ic.poly(apron, "#8c7858", "#4e4232", noise=0.34)
    ic.shade(ic.poly_mask([(84, 902), (330, 892), (350, 950), (74, 955)]), (84, 94, 112), 0.35, blur=10)

    # ---- windlass over the shaft (the identity), with its shadow on the rock behind
    xl, xr, wtop, wbase = 372, 660, 538, 904
    tint(ic, ic.poly_mask([(xl + 30, wtop + 20), (xr + 110, wtop + 20), (xr + 140, wbase), (xl + 60, wbase)]), rock,
         (10, 6, 4), 0.48, 22)
    windlass(ic, xl, xr, wtop, wbase, 580, 704)

    # ---- heap of cubic galena, bottom right
    cube_heap(ic, 690, 1016, 986, 670, 52, 5)

    # ---- basket of ore and a pick, bottom left
    ic.line([(262, 962), (330, 800)], 18, DARK)
    ic.line([(262, 962), (330, 800)], 10, (140, 102, 64))
    ic.draw.arc((268, 764, 394, 838), 185, 335, fill=DARK + (255,), width=20)
    ic.draw.arc((268, 764, 394, 838), 187, 333, fill=IRON + (255,), width=12)
    for x, y, s in ((88, 852, 40), (132, 842, 46), (178, 856, 38), (110, 868, 34), (156, 870, 36)):
        cube(ic, x, y, s, ic.random.uniform(-25, 25))
    ic.basket(52, 866, 222, 974, colors=("#b08a58", "#62462a"))
    tint(ic, ic.mask("rectangle", (172, 862, 232, 980)), None, (0, 0, 0), 0.22, 10)
