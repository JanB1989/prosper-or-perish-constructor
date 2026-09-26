"""Sugarcane Farm: a tall stand of cane beside a small thatched field hut, cut cane bundled in front.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/sugarcane_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/sugarcane_farm

Identity: jointed yellow-green cane stalks crowned by long arching blades, taller than the hut
they stand beside; tied bundles of cut cane with pale cut ends stacked at the bottom right.
Tier 0 of the cane chain (the Trapiche farm adds the roller mill and boiling house).

Local helpers: ``blade`` (long narrow arching grass leaf), ``stalk`` (jointed cane stem shaded
across its width), ``stand`` (clump of cane back to front, dead trash leaves low down),
``cut_cane`` (lying stalk with a pale cut end), ``cane_bundle`` (tied stack of cut cane),
``thatch`` (from coffee_grove), ``union``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("sugar_plantation", "fiber_crops_farm", "farming_village", "tobacco_plantation")

BLADE = ("#9aac52", "#2a4012")
BLADE_BACK = ("#5e7a36", "#16260c")
TRASH = ("#b09a62", "#5a4428")
STALKS = (("#c8c062", "#5e6024"), ("#bab454", "#545620"), ("#a8745a", "#4a2e22"), ("#c2b25e", "#5a4e22"),
          ("#9e6468", "#44262c"), ("#aa705e", "#4a2a24"))
CUT = (("#bcb466", "#4e4a1e"), ("#b0a45a", "#4a4020"), ("#a67a58", "#482c20"))


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def blade(ic: Icon, base, deg: float, length: float, width: float, droop: float = 0.5, colors=BLADE,
          acc: list | None = None, xmin: float | None = None) -> None:
    """Long narrow cane blade from ``base`` towards ``deg`` (0 = right, -90 = up), arching over under
    its weight; shaded lower half, pale midrib. A blade reaching left of ``xmin`` is shortened so the
    stand keeps a ragged fan of tips inside the canvas."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    if xmin is not None and d[0] < 0:
        edge = xmin + 60 * abs(math.sin(b[0] * 1.7 + b[1] * 0.3 + deg))
        reach = -d[0] * length
        if b[0] - reach < edge:
            length *= max(0.35, (b[0] - edge) / reach)
    ts = np.linspace(0, 1, 26)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * min(1.0, t * 7) * (1 - t) ** 0.7 for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], radial=(min(xs), min(ys), max(length, 1) * 1.05), noise=0.2, chroma=0.12)
    lower = s1 if n[1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (8, 16, 4), 0.32)
    ic.line([tuple(p) for p in spine[1:-6]], 3, (206, 214, 160, 110))
    ic.outline(pts, 3, (18, 28, 8, 130))
    if acc is not None:
        acc[0] = union(acc[0], m)


def stalk(ic: Icon, x: float, base: float, h: float, lean: float, w: float, colors, joint: float = 46,
          acc: list | None = None) -> list:
    """Jointed cane stem from (x, base) rising ``h`` and bending ``lean`` px sideways at the top.

    Lit on the left, dark on the right; each joint is a dark ring under a pale waxy band.
    Returns the spine points (bottom to top)."""
    ts = np.linspace(0, 1, 24)
    spine = [np.array([x + lean * t * t, base - h * t]) for t in ts]
    hws = [w / 2 * (1.0 - 0.35 * t) for t in ts]
    left = [tuple(p - np.array([hw, 0])) for p, hw in zip(spine, hws)]
    right = [tuple(p + np.array([hw, 0])) for p, hw in zip(spine, hws)]
    pts = left + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], (x - w * 0.6, x + lean + w * 0.6), vertical=False, noise=0.18)
    ic.shade(ic.intersect(m, ic.poly_mask([tuple(p) for p in spine] + right[::-1])), (10, 10, 0), 0.22)
    y = base - ic.random.uniform(10, 30)
    while y > base - h + 30:
        t = (base - y) / h
        cx = x + lean * t * t
        hw = w / 2 * (1.0 - 0.35 * t) + 1
        ic.line([(cx - hw, y), (cx + hw, y + 2)], 4, (40, 34, 14, 200))
        ic.line([(cx - hw + 2, y - 5), (cx + hw - 2, y - 3)], 3, (236, 232, 196, 110))
        y -= joint * ic.random.uniform(0.85, 1.15)
    ic.outline(pts, 3, (30, 26, 10, 170))
    if acc is not None:
        acc[0] = union(acc[0], m)
    return [tuple(p) for p in spine]


def stand(ic: Icon, x0: float, x1: float, base0: float, base1: float, h0: float, h1: float, n: int) -> Image.Image:
    """A clump of cane: a dark leafy mass, then ``n`` stalks from back (base0, h0) to front (base1, h1),
    each crowned with long arching blades. Returns its mask."""
    rnd = ic.random
    acc = [blank()]
    # shaded interior of the clump so no gaps open between the stalks; kept inside the stand so its
    # edges hide behind the stalks and blades
    top = [(x, base0 - h0 * rnd.uniform(0.6, 0.78)) for x in np.linspace(x0 + 70, x1 - 60, 12)]
    mass = [(x0 + 110, base1 - 10), (x0 + 90, base1 - h0 * 0.2), (x0 + 60, base0 - h0 * 0.45)] + top + [(x1 - 10, base0 - h0 * 0.4), (x1 - 30, base1 - 10)]
    mm = ic.poly_mask(mass)
    ic.fill(mm, "#4a6430", "#22341a", (min(p[1] for p in top), base1), noise=0.3)
    acc[0] = union(acc[0], mm)
    for _ in range(int(n * 5)):  # shadowed blades inside the mass
        x = rnd.uniform(x0, x1)
        y = rnd.uniform(base0 - h0 * 0.8, base0 - h0 * 0.2)
        side = rnd.choice((-1, 1))
        blade(ic, (x, y), (0 if side > 0 else 180) - side * rnd.uniform(20, 70), h0 * rnd.uniform(0.25, 0.4),
              rnd.uniform(20, 28), rnd.uniform(0.6, 1.2), BLADE_BACK, acc, xmin=24)
    items = sorted((rnd.random(), rnd.uniform(x0, x1)) for _ in range(n))
    for depth, x in items:
        base = base0 + (base1 - base0) * depth + rnd.uniform(-8, 8)
        h = (h0 + (h1 - h0) * depth) * rnd.uniform(0.86, 1.08)
        lean = rnd.uniform(-50, 50)
        f = 0.7 + 0.38 * depth
        cols = rnd.choice(STALKS)
        cols = tuple(tuple(int(min(255, v * f)) for v in rgb(c)) for c in cols)
        bl = tuple(tuple(int(min(255, v * (0.8 + 0.3 * depth))) for v in rgb(c)) for c in (BLADE if depth > 0.3 else BLADE_BACK))
        w = rnd.uniform(24, 30) * (0.85 + 0.2 * depth)
        for k in range(rnd.randint(1, 2)):  # dead trash leaves clinging low down
            yy = base - h * rnd.uniform(0.15, 0.4)
            side = rnd.choice((-1, 1))
            blade(ic, (x + side * 4, yy), 90 + side * -rnd.uniform(40, 70), h * rnd.uniform(0.2, 0.3), 22,
                  0.2, TRASH, acc, xmin=24)
        spine = stalk(ic, x, base, h * 0.74, lean, w, cols, joint=52, acc=acc)
        tip = spine[-1]
        side = rnd.choice((-1, 1))
        for k in range(rnd.randint(6, 8)):
            s = rnd.uniform(0.68, 1.0)
            p = spine[int(s * (len(spine) - 1))]
            ang = (0 if side > 0 else 180) - side * rnd.uniform(30, 72)
            blade(ic, p, ang, h * rnd.uniform(0.44, 0.6), rnd.uniform(32, 40), rnd.uniform(0.8, 1.4), bl, acc, xmin=24)
            side = -side
        for k in range(rnd.randint(2, 3)):  # the upright spindle of young leaves
            blade(ic, tip, -90 + rnd.uniform(-26, 26), h * rnd.uniform(0.22, 0.32), rnd.uniform(24, 30),
                  rnd.uniform(0.2, 0.6), bl, acc, xmin=24)
    return acc[0]


def close_gaps(ic: Icon, region: Image.Image, size: int = 17, colors=("#5a7236", "#34481e")) -> None:
    """Paint shaded foliage *behind* the art only where it is enclosed: pockets fully surrounded by
    blades, and gaps narrower than ``size`` px, so the silhouette outline does not flood them with
    black. The outer hull is left alone, so the silhouette follows the blade tips."""
    from PIL import ImageDraw
    al = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    closed = al.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    pad = Image.new("L", (SIZE + 2, SIZE + 2), 0)
    pad.paste(al, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    holes = pad.crop((1, 1, SIZE + 1, SIZE + 1)).point(lambda v: 255 if v == 0 else 0)
    gap = ic.intersect(union(ImageChops.subtract(closed, al), holes), region)
    back = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    a, b = rgb(colors[0]), rgb(colors[1])
    t = np.clip((np.mgrid[0:SIZE, 0:SIZE][0] - 200) / 700, 0, 1)[..., None]
    layer = (a * (1 - t) + b * t) * (1 + 0.25 * ic.noise)[..., None]
    tex = Image.fromarray(np.clip(layer, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    rnd = ic.random
    box = gap.getbbox()

    def strokes(dr):  # far blades: soft arching strokes in mid tones, no dark outlines
        if not box:
            return
        for _ in range(700):
            x, y = rnd.uniform(box[0], box[2]), rnd.uniform(box[1], box[3])
            L = rnd.uniform(30, 70)
            ang = math.radians(rnd.choice((-1, 1)) * rnd.uniform(10, 60) + rnd.choice((0, 180)))
            pts = [(x + math.cos(ang) * L * t, y + math.sin(ang) * L * t + 0.4 * L * t * t) for t in (0, 0.5, 1)]
            col = (120, 142, 72, 90) if rnd.random() < 0.5 else (40, 58, 24, 80)
            dr.line(pts, fill=col, width=int(rnd.uniform(6, 10)))

    strokes(ImageDraw.Draw(tex))
    back.paste(tex, (0, 0), gap)
    ic.image.paste(Image.alpha_composite(back, ic.image), (0, 0))


def cut_cane(ic: Icon, p0, p1, r: float, colors, joint: float = 44) -> None:
    """Lying cut stalk from ``p0`` (cut end, facing the viewer's left) to ``p1``; radius ``r``."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-d[1], d[0]])
    if n[1] > 0:
        n = -n  # n points up
    pts = [tuple(p0 + n * r), tuple(p1 + n * r * 0.9), tuple(p1 - n * r * 0.9), tuple(p0 - n * r)]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, colors[0], colors[1], (min(ys), max(ys)), noise=0.18)
    ic.shade(ic.intersect(m, ic.poly_mask([tuple(p0 + n * r * 0.55), tuple(p1 + n * r * 0.5),
                                            tuple(p1 + n * r * 0.1), tuple(p0 + n * r * 0.15)])),
             (250, 246, 210), 0.22, blur=2)
    L = float(np.linalg.norm(p1 - p0))
    s = ic.random.uniform(20, joint)
    while s < L - 10:
        c = p0 + d * s
        ic.line([tuple(c + n * r), tuple(c - n * r)], 4, (40, 34, 14, 190))
        ic.line([tuple(c + d * 5 + n * r * 0.9), tuple(c + d * 5 - n * r * 0.9)], 3, (236, 232, 196, 90))
        s += joint * ic.random.uniform(0.85, 1.15)
    ic.outline(pts, 3, (30, 26, 10, 170))
    # pale fibrous cut end
    e = (p0[0] - r * 0.6, p0[1] - r, p0[0] + r * 0.6, p0[1] + r)
    ic.fill(ic.mask("ellipse", e), "#e2dcb2", "#a89c6a", radial=(p0[0] - r * 0.3, p0[1] - r * 0.5, r * 1.6), noise=0.12)
    ic.overlay(lambda dr: dr.ellipse(e, outline=(70, 70, 30, 200), width=3))


def cane_bundle(ic: Icon, x: float, y: float, length: float, r: float, rows: int = 3, tilt: float = 6) -> None:
    """Pyramid of cut cane lying with the pale cut ends towards the viewer's left, bodies running back
    to the right; (x, y) = cut end of the front bottom stalk. Ends further back sit a little higher."""
    rnd = ic.random
    t = math.radians(tilt)
    d = np.array([math.cos(t), -math.sin(t)])
    ends = []
    for k in range(rows):
        for j in reversed(range(rows - k)):
            ex = x + j * r * 1.25 + k * r * 0.62 + rnd.uniform(-8, 8)
            ey = y - k * r * 1.68 - j * r * 0.32
            ends.append((ex, ey))
    for ex, ey in ends:
        L = length * rnd.uniform(0.9, 1.04)
        cut_cane(ic, (ex, ey), (ex + d[0] * L, ey + d[1] * L), r, rnd.choice(CUT))
    # rope ties around the pile
    top_y = y - (rows - 1) * r * 1.68 - r
    for f in (0.34, 0.74):
        cx = x + length * f
        yy = -math.tan(t) * length * f
        ic.line([(cx + r * 0.8, top_y + yy - 4), (cx - 4, y + yy + r + 2)], 13, (74, 56, 30))
        ic.line([(cx + r * 0.8 - 3, top_y + yy), (cx - 5, y + yy + r - 2)], 5, (184, 158, 104, 170))


def thatch(ic: Icon, ridge, eave, c=("#b8a06a", "#6c5632"), lip_c=("#8a7040", "#4e3c1e"),
           ridge_c=((104, 84, 50), (150, 128, 84, 170))) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.24, 0.47, 0.7, 1.0]
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
        tint = rnd.uniform(0.92, 1.06)
        ic.fill(band, tuple(int(v * tint) for v in rgb(c[0])), tuple(int(v * tint) for v in rgb(c[1])), (y0 - 10, y1 + 30),
                noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, y1=y1, low=low):
            for _ in range(240):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), lip_c[0], lip_c[1], (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 22, ridge_c[0])
    ic.line([tuple(p) for p in ridge], 8, ridge_c[1])


def hut(ic: Icon) -> None:
    """Small daub-walled field hut with a thatched roof and a dark doorway, back right."""
    rnd = ic.random
    L, R, TOP, BASE = 560, 930, 560, 850
    ic.rect((L, TOP, R, BASE), "#b89c70", "#7e6444", noise=0.28, edge=0)
    for _ in range(30):  # patchy daub
        x, y = rnd.uniform(L, R), rnd.uniform(TOP, BASE)
        ic.shade(ic.mask("ellipse", (x - 22, y - 12, x + 22, y + 12)), (255, 240, 210) if rnd.random() < 0.5 else (40, 26, 12),
                 0.14, blur=5)
    ic.shade(ic.mask("rectangle", (L, BASE - 60, R, BASE)), (40, 30, 16), 0.35, blur=18)  # damp grime
    for x in (L + 8, 742, R - 8):
        ic.rect((x - 13, TOP, x + 13, BASE), "#8a6442", "#4a3220", vertical=False, noise=0.2, edge=3)
    ic.door(780, 668, 872, BASE, arched=False, surround=None)
    ic.shade(ic.mask("rectangle", (782, 670, 870, BASE)), (0, 0, 0), 0.35)
    ic.window(626, 660, 680, 716)
    ic.shade(ic.mask("rectangle", (L, TOP, R, TOP + 70)), alpha=0.5, blur=14)
    ic.outline([(L, TOP), (R, TOP), (R, BASE), (L, BASE)])
    ridge = [(610, 408), (752, 398), (900, 406)]
    eave = [(x, 580 + rnd.uniform(-5, 7)) for x in np.linspace(528, 968, 18)]
    # straw ochre, a step lighter than the cane crowns so the roof stands apart from them
    thatch(ic, ridge, eave, ("#d6b56c", "#8e6a34"), ("#a4804a", "#5e4420"), ((132, 104, 58), (196, 168, 110, 170)))
    ic.shade(ic.poly_mask([(800, 360), (1000, 360), (1000, 620), (820, 620)]), alpha=0.18, blur=50)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.86

    hut(ic)
    # irregular patch of reddish field soil, its left end rounded off under the cane
    top = [(x, 900 + 16 * max(0.0, (320 - x) / 150) + rnd.uniform(-10, 10)) for x in np.linspace(170, 960, 14)]
    bottom = [(x, 994 + rnd.uniform(-6, 6)) for x in np.linspace(930, 190, 8)]
    cap = [(170 + 118 * math.cos(a) + rnd.uniform(-5, 5), 958 + 42 * math.sin(a)) for a in np.linspace(math.pi * 0.55, math.pi * 1.45, 9)]
    ground = top + [(1004, 916), (1012, 956), (998, 990)] + bottom + cap
    ic.poly(ground, "#7a5438", "#4c3222", noise=0.34, edge=3)
    for _ in range(60):  # clods and dry crumbs
        x, y = rnd.uniform(90, 990), rnd.uniform(915, 990)
        r = rnd.uniform(8, 16)
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.45, x + r, y + r * 0.45)),
                 (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)

    # the cane stand, left: taller than the hut
    m = stand(ic, 90, 560, 900, 972, 760, 860, 15)
    close_gaps(ic, ic.mask("ellipse", (-60, 60, 700, 1100)).filter(ImageFilter.GaussianBlur(30)), 17)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (380, 300, 1000, 1100))), (6, 12, 4), 0.22, blur=40)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 760, SIZE, SIZE))), (10, 14, 4), 0.35, blur=30)
    ic.shade(ic.mask("ellipse", (40, 950, 640, 1010)), alpha=0.35, blur=12)

    # cut cane bundles, bottom right
    ic.shade(ic.mask("ellipse", (560, 950, 1016, 1004)), alpha=0.45, blur=10)
    cane_bundle(ic, 600, 950, 330, 30, rows=3, tilt=7)
