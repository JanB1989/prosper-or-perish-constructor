"""Trapiche Sugarcane Farm: an ox-driven three-roller cane mill before a stone boiling house.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build     --script ../ProsperOrPerishConstructor/assets/icon_drawings/trapiche_sugarcane_farm/draw.py     --out ../ProsperOrPerishConstructor/artifacts/icons/trapiche_sugarcane_farm

Identity: the trapiche (three iron-banded upright rollers in a timber frame, a sweep beam to a
draught ox) in front of a tiled boiling house with glowing furnace mouths and a smoking brick
chimney; the cane stand behind at the left and cut cane stacked in front. Tier 1 of the cane chain:
same cane, bundles and palette as the Sugarcane Farm, plus the mill, the fire and masonry.

Local helpers: ``blade``, ``stalk``, ``stand``, ``close_gaps``, ``cut_cane``, ``cane_bundle`` (as in
sugarcane_farm), ``tint``, ``stones``, ``shingles``, ``smoke``, ``flame`` (from cookshop), ``timber``
(squared beam at any angle), ``roller`` (upright banded drum), ``ox`` (draught ox with yoke),
``boiling_house``, ``mill``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 37
REFS = ("sugar_plantation", "windmill", "brewery_mill", "farming_village")

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


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines (from cookshop)."""
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
    """Roof plane of overlapping tiles, each with its own tone, courses shading the one below (from cookshop)."""
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


def smoke(ic: Icon, x: float, y: float, length: float, drift: float) -> None:
    """Soft tapering plume from a chimney top at (x, y): a thin grey thread at the mouth that widens,
    pales and breaks into a last wisp as it rises and drifts. Shaped by a soft grey gradient only,
    no drawn outline; kept opaque because the icon outline sits behind any see-through pixel."""
    alpha = Image.new("L", (SIZE, SIZE), 0)
    light = Image.new("L", (SIZE, SIZE), 0)
    da, dl = ImageDraw.Draw(alpha), ImageDraw.Draw(light)
    for t in np.linspace(0, 1, 70):
        if 0.74 < t < 0.8:
            continue  # the plume breaks up into a last wisp
        cx = x + drift * t ** 1.2 + 10 * math.sin(t * 6.5)
        cy = y - length * t
        r = 8 + 30 * math.sin(min(t, 0.95) * math.pi * 0.62) * (1.0 if t < 0.8 else 0.75)
        da.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=255)
        dl.ellipse((cx - r * 0.95, cy - r * 0.85, cx + r * 0.2, cy + r * 0.1), fill=255)
    alpha = alpha.filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(255, int(v * 1.6)))
    light = light.filter(ImageFilter.GaussianBlur(9))
    tt = np.clip((y - ic._yy) / length, 0, 1)[..., None]
    base = np.array((128, 124, 120)) * (1 - tt) + np.array((214, 210, 204)) * tt
    lit = np.asarray(light, float)[..., None] / 255
    col = base * (1 - 0.4 * lit) + np.array((238, 236, 230)) * 0.4 * lit
    col = col * (1 + 0.05 * ic.noise)[..., None]
    lay = Image.fromarray(np.clip(col, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    lay.putalpha(alpha)
    ic.image.alpha_composite(lay)


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#ffbe55", "#c9451c"), inner=("#fff3c4", "#ffb449")) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one (from cookshop)."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (inner, 0.5, 0.62)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def timber(ic: Icon, p0, p1, width: float, c1="#8e6642", c2="#4a3220") -> None:
    """Squared beam lit along its upper edge, grain along its length."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-d[1], d[0]])
    if n[1] > 0:
        n = -n
    hw = width / 2
    pts = [tuple(p0 + n * hw), tuple(p1 + n * hw), tuple(p1 - n * hw), tuple(p0 - n * hw)]
    m = ic.poly_mask(pts)
    if abs(d[0]) > abs(d[1]):
        ys = [p[1] for p in pts]
        ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    else:
        xs = [p[0] for p in pts]
        ic.fill(m, c1, c2, (min(xs), max(xs)), vertical=False, noise=0.2)
    ic.line([tuple(p0 + n * hw * 0.6), tuple(p1 + n * hw * 0.6)], 3, (230, 200, 160, 80))
    ic.line([tuple(p0 - n * hw * 0.2), tuple(p1 - n * hw * 0.1)], 2, (40, 26, 14, 90))
    ic.outline(pts, 4, (40, 26, 14, 200))


def roller(ic: Icon, cx: float, top: float, bottom: float, r: float) -> None:
    """Upright trapiche roller: a tall fluted hardwood drum, lit on the left, light and dark flutes
    foreshortened round the cylinder, one thin iron band at the top and one at the bottom."""
    m = ic.mask("rectangle", (cx - r, top, cx + r, bottom))
    ic.fill(m, "#a07650", "#2a1a0c", (cx - r * 0.9, cx + r), vertical=False, noise=0.18)
    tint(ic, ic.mask("rectangle", (cx - r * 0.66, top, cx - r * 0.3, bottom)), m, (255, 236, 200), 0.3, 4)

    def flutes(dr):
        for k, th in enumerate(np.linspace(-1.35, 1.35, 11)):
            gx = cx + r * math.sin(th)
            w = max(2, int(5 * math.cos(th)))
            lit = th < 0.3
            dr.line([(gx, top + 10), (gx, bottom - 10)], fill=(20, 12, 6, 150), width=w)
            dr.line([(gx - w, top + 10), (gx - w, bottom - 10)], fill=(255, 232, 196, 60 if lit else 14), width=max(2, w - 1))

    ic.overlay(flutes, m)
    for f in (0.0, 1.0):
        y = top + 7 if f == 0 else bottom - 7
        b = ic.mask("rectangle", (cx - r - 2, y - 7, cx + r + 2, y + 7))
        ic.fill(b, "#8a8884", "#26262a", (cx - r, cx + r), vertical=False, noise=0.1)
    ic.shade(ic.mask("rectangle", (cx - r, top + 10, cx + r, top + 40)), alpha=0.3, blur=8)
    ic.outline([(cx - r, top), (cx + r, top), (cx + r, bottom), (cx - r, bottom)], 3, (30, 20, 12, 170))


def cog(ic: Icon, cx: float, cy: float, rx: float, ry: float, teeth: int = 14, h: float = 14) -> None:
    """Crown gear seen from slightly above: a short iron-shod wheel with square teeth round its rim."""
    body = union(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)),
                 union(ic.mask("rectangle", (cx - rx, cy, cx + rx, cy + h)),
                       ic.mask("ellipse", (cx - rx, cy + h - ry, cx + rx, cy + h + ry))))
    ic.fill(body, "#8a6440", "#2e1e10", (cx - rx, cx + rx), vertical=False, noise=0.2)
    for k in range(teeth):  # teeth on the front half of the rim, drawn back to front
        a = math.pi * (k + 0.5) / teeth
        tx, ty = cx - rx * math.cos(a), cy + ry * math.sin(a)
        tw = 8 + 4 * math.sin(a)
        ic.poly([(tx - tw / 2, ty - 10), (tx + tw / 2, ty - 10), (tx + tw / 2, ty + h - 2), (tx - tw / 2, ty + h - 2)],
                "#9a9690" if a > math.pi / 2 else "#6a6660", "#2a2a2a", edge=2)
    top = ic.mask("ellipse", (cx - rx + 6, cy - ry + 2, cx + rx - 6, cy + ry - 2))
    ic.fill(top, "#b08a5e", "#5a3e24", radial=(cx - rx * 0.4, cy - ry, rx * 1.6), noise=0.2)
    ic.overlay(lambda d: d.ellipse((cx - rx * 0.62, cy - ry * 0.62, cx + rx * 0.62, cy + ry * 0.62),
                                   outline=(60, 58, 54, 200), width=5))
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry + h), outline=(36, 24, 14, 200), width=3))


def limb(ic: Icon, pts, widths, colors) -> Image.Image:
    """Jointed leg along ``pts`` (top to hoof) with a width per point; lit on the left. Returns its mask."""
    P = [np.array(p, float) for p in pts]
    left, right = [], []
    for i, p in enumerate(P):
        d = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        d /= np.linalg.norm(d)
        n = np.array([d[1], -d[0]])
        left.append(tuple(p - n * widths[i] / 2))
        right.append(tuple(p + n * widths[i] / 2))
    poly = left + right[::-1]
    m = ic.poly_mask(poly)
    xs = [q[0] for q in poly]
    ic.fill(m, colors[0], colors[1], (min(xs), max(xs)), vertical=False, noise=0.18)
    return m


def hoof(ic: Icon, x: float, y: float, w: float = 26) -> Image.Image:
    """Small cloven hoof standing at (x, y): two dark claws with a lit front edge."""
    m = Image.new("L", (SIZE, SIZE), 0)
    for sx in (-1, 1):
        q = [(x + sx * 1.5, y - 14), (x + sx * w * 0.42, y - 14), (x + sx * w * 0.55, y), (x + sx * 2, y)]
        qm = ic.poly_mask(q)
        ic.fill(qm, "#4a3c30", "#161210", (y - 14, y), noise=0.1)
        m = union(m, qm)
    ic.line([(x - w * 0.42, y - 12), (x - 2, y - 12)], 3, (150, 130, 110, 120))
    return m


def ox(ic: Icon, x: float, y: float) -> tuple[float, float]:
    """Draught ox walking left, head low, neck yoke with its bow; (x, y) = front of the withers.

    Rounded barrel with a hump over the withers, lighter back and darker belly, jointed legs two
    tones darker than the coat on small cloven hooves, horns curving forward. Only the outer
    silhouette is edged. Returns where the sweep beam meets the yoke."""
    coat = ("#b27c52", "#4a2c1a")
    legc = ("#7e5438", "#2a180e")
    farc = ("#5e3e2a", "#1e140c")
    whole = Image.new("L", (SIZE, SIZE), 0)
    # far legs (fore and hind) in shadow behind the body
    for pts, ws in (([(x + 70, y + 92), (x + 66, y + 172), (x + 72, y + 222), (x + 74, y + 234)], [40, 20, 15, 15]),
                    ([(x + 214, y + 80), (x + 238, y + 170), (x + 226, y + 222), (x + 228, y + 234)], [48, 20, 15, 15])):
        whole = union(whole, limb(ic, pts, ws, farc))
        whole = union(whole, hoof(ic, pts[-1][0], pts[-1][1] + 6, 24))
    # far horn
    ic.line([(x - 14, y + 18), (x - 18, y - 2), (x - 30, y - 18), (x - 46, y - 22), (x - 56, y - 14)], 10, (110, 96, 76))
    ic.line([(x - 46, y - 22), (x - 56, y - 14)], 6, (40, 32, 24))
    # near legs: fore reaching forward, hind with a bent hock
    for pts, ws in (([(x + 40, y + 92), (x + 26, y + 168), (x + 12, y + 222), (x + 8, y + 236)], [46, 22, 16, 16]),
                    ([(x + 194, y + 70), (x + 186, y + 138), (x + 214, y + 176), (x + 198, y + 224), (x + 196, y + 236)],
                     [60, 36, 20, 16, 16])):
        lm = limb(ic, pts, ws, legc)
        whole = union(whole, lm)
        k = pts[-3]
        tint(ic, ic.mask("ellipse", (k[0] - 14, k[1] - 12, k[0] + 14, k[1] + 12)), lm, (250, 220, 190), 0.18, 4)
        whole = union(whole, hoof(ic, pts[-1][0], pts[-1][1] + 6, 26))
    # body: barrel, chest, hump over the withers, rump and thighs
    parts = [(x + 30, y - 2, x + 258, y + 142), (x - 6, y + 6, x + 112, y + 136), (x + 18, y - 22, x + 90, y + 36),
             (x + 176, y - 8, x + 262, y + 108), (x + 172, y + 20, x + 244, y + 166),
             (x + 10, y + 50, x + 76, y + 160)]
    bm = Image.new("L", (SIZE, SIZE), 0)
    for e in parts:
        bm = union(bm, ic.mask("ellipse", e))
    ic.fill(bm, coat[0], coat[1], radial=(x + 70, y - 24, 330), noise=0.2)
    tint(ic, ic.mask("ellipse", (x + 10, y + 86, x + 270, y + 200)), bm, (24, 12, 6), 0.5, 22)  # darker belly
    tint(ic, ic.mask("ellipse", (x + 6, y - 44, x + 250, y + 36)), bm, (255, 236, 206), 0.22, 16)  # lit back
    tint(ic, ic.mask("ellipse", (x + 100, y + 20, x + 160, y + 130)), bm, (30, 16, 8), 0.2, 16)  # behind the shoulder
    tint(ic, ic.mask("ellipse", (x + 16, y + 10, x + 80, y + 96)), bm, (255, 236, 206), 0.14, 10)  # shoulder
    tint(ic, ic.mask("ellipse", (x + 196, y - 4, x + 240, y + 34)), bm, (255, 236, 206), 0.16, 8)  # hip bone
    tint(ic, ic.mask("ellipse", (x + 170, y + 110, x + 250, y + 180)), bm, (20, 10, 4), 0.3, 12)  # thigh underside
    whole = union(whole, bm)
    # tail from the rump, tapering to a dark switch
    ic.line([(x + 256, y + 16), (x + 268, y + 70), (x + 266, y + 130), (x + 262, y + 168)], 9, (96, 62, 40))
    ic.ellipse((x + 252, y + 160, x + 274, y + 200), "#3a2a1e", "#140e0a", edge=0)
    tm = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(tm).line([(x + 256, y + 16), (x + 268, y + 70), (x + 266, y + 130), (x + 262, y + 168)], fill=255, width=9)
    ImageDraw.Draw(tm).ellipse((x + 252, y + 160, x + 274, y + 200), fill=255)
    whole = union(whole, tm)
    # neck and dewlap reaching forward and down
    neck = [(x + 44, y - 12), (x - 6, y + 14), (x - 36, y + 58), (x - 30, y + 108), (x + 8, y + 124), (x + 44, y + 104)]
    nm = ic.poly_mask(neck)
    ic.fill(nm, "#b8845a", "#5a3620", radial=(x, y, 170), noise=0.2)
    dew = [(x - 22, y + 96), (x - 2, y + 150), (x + 26, y + 148), (x + 36, y + 106)]
    dm = ic.poly_mask(dew)
    ic.fill(dm, "#7a5034", "#3a2214", (y + 96, y + 150), noise=0.2)
    whole = union(whole, union(nm, dm))
    # head, forehead lit, dark muzzle
    head = [(x - 16, y + 12), (x - 50, y + 26), (x - 70, y + 64), (x - 90, y + 108), (x - 88, y + 130), (x - 66, y + 138),
            (x - 44, y + 124), (x - 22, y + 86), (x - 2, y + 58)]
    hm = ic.poly_mask(head)
    ic.fill(hm, "#c08c62", "#4a2c1c", radial=(x - 40, y + 30, 130), noise=0.18)
    tint(ic, ic.mask("ellipse", (x - 100, y + 100, x - 58, y + 142)), hm, (50, 38, 32), 0.55, 5)
    tint(ic, ic.mask("ellipse", (x - 40, y + 70, x + 0, y + 130)), hm, (30, 16, 8), 0.3, 10)  # cheek shadow
    ic.ellipse((x - 86, y + 118, x - 76, y + 126), "#140e0a", "#140e0a", edge=0)  # nostril
    ic.ellipse((x - 50, y + 56, x - 38, y + 66), "#120c0a", "#120c0a", edge=0)  # eye
    ic.line([(x - 48, y + 58), (x - 44, y + 57)], 2, (220, 210, 190, 160))
    whole = union(whole, hm)
    # ear, near horn curving forward
    ear = [(x - 6, y + 34), (x + 30, y + 34), (x + 20, y + 50), (x - 2, y + 48)]
    ic.poly(ear, "#9e6a44", "#3e2416", edge=0)
    horn = [(x - 24, y + 24), (x - 32, y + 2), (x - 48, y - 12), (x - 68, y - 14), (x - 82, y - 4)]
    for w, col in ((15, (60, 48, 36)), (10, (206, 190, 158))):
        ic.line(horn[:4], w, col)
        ic.line(horn[3:], max(4, w - 5), col)
    ic.line(horn[3:], 5, (46, 36, 26))
    # yoke over the neck in front of the hump, bow round the neck
    yoke = [(x - 22, y - 10), (x + 30, y - 26), (x + 40, y - 2), (x - 14, y + 14)]
    ic.poly(yoke, "#9a7048", "#3e2a18", edge=0)
    ic.line([yoke[0], yoke[1]], 4, (230, 200, 160, 110))
    bow = [(x - 14, y + 8), (x - 30, y + 56), (x - 22, y + 100), (x + 2, y + 116), (x + 22, y + 104), (x + 26, y + 60)]
    ic.line(bow, 12, (64, 44, 26))
    ic.line(bow, 6, (184, 150, 104))
    # only the outer silhouette is edged
    edge = ImageChops.subtract(whole, whole.filter(ImageFilter.MinFilter(7)))
    ic.shade(edge, (30, 18, 10), 0.7)
    return (x + 6, y - 14)


def boiling_house(ic: Icon) -> None:
    """Rubble-stone boiling house with a tiled roof, furnace mouths glowing low in the front wall
    and a tall brick chimney trailing smoke."""
    rnd = ic.random
    L, R, TOP, BASE = 540, 990, 560, 872
    # chimney (behind the roof at the right end)
    CX0, CX1 = 846, 936
    cm = ic.mask("rectangle", (CX0, 250, CX1, 600))
    ic.fill(cm, "#a86a4e", "#5a3024", (CX0, CX1), vertical=False, noise=0.22)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k, y in enumerate(range(250, 600, 18)):
        d.line([(CX0, y), (CX1, y)], fill=(210, 184, 160, 60), width=3)
        for x in range(CX0 + (k % 2) * 18, CX1, 36):
            d.line([(x, y), (x, y + 18)], fill=(40, 20, 12, 60), width=3)
    clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), cm)
    ic.image.alpha_composite(clip)
    tint(ic, ic.mask("rectangle", (CX1 - 22, 250, CX1, 600)), cm, (20, 8, 4), 0.35, 6)
    ic.outline([(CX0, 250), (CX1, 250), (CX1, 600), (CX0, 600)], 4)
    ic.rect((CX0 - 12, 234, CX1 + 12, 256), "#9a8c7c", "#5a5046", edge=4)
    ic.rect((CX0 + 12, 238, CX1 - 12, 250), "#1a1410", "#1a1410", edge=0)
    # walls
    stones(ic, (L, TOP, R, BASE), "#a89070", "#6a5640", course=34)
    ic.shade(ic.mask("rectangle", (L, BASE - 70, R, BASE)), (40, 32, 20), 0.3, blur=20)
    # one furnace mouth at the gable end, fire inside
    fx, w = 952, 56
    mouth = union(ic.mask("ellipse", (fx - w / 2, BASE - 120, fx + w / 2, BASE - 64)),
                  ic.mask("rectangle", (fx - w / 2, BASE - 92, fx + w / 2, BASE)))
    ic.fill(mouth.filter(ImageFilter.MaxFilter(19)), "#c8b89e", "#8a7a64", (BASE - 140, BASE), noise=0.2)
    ic.fill(mouth, "#241810", "#0e0806", (BASE - 120, BASE), noise=0.1)
    flame(ic, fx, BASE - 2, w * 0.8, 56)
    # small dark window high up
    ic.window(660, 616, 710, 660)
    ic.window(812, 616, 862, 660)
    ic.outline([(L, TOP), (R, TOP), (R, BASE), (L, BASE)])
    # tiled roof
    roof = [(L - 34, TOP + 14), (R + 30, TOP + 14), (R - 26, 404), (L + 20, 404)]
    shingles(ic, roof, "#b86e4e", "#6a3424", course=30, stagger=40)
    ic.rect((L + 14, 390, R - 20, 410), "#a0664a", "#5a3020", edge=4)
    ic.shade(ic.mask("rectangle", (L, TOP + 10, R, TOP + 70)), alpha=0.45, blur=12)
    ic.shade(ic.poly_mask([(800, 380), (1030, 380), (1030, 600), (840, 600)]), alpha=0.18, blur=50)
    # chimney top shows above the ridge, smoke drifting left
    smoke(ic, 891, 230, 130, -90)


def mould(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Clay sugar-loaf mould: an inverted cone standing point down in its drip pot, pale clay cap on top."""
    pot = (cx - w * 0.36, base - h * 0.34, cx + w * 0.36, base)
    ic.fill(ic.mask("ellipse", pot), "#a0704a", "#46281a", radial=(pot[0] + 6, pot[1] + 4, w * 0.8), noise=0.2)
    cone = [(cx - w / 2, base - h), (cx + w / 2, base - h), (cx + 4, base - h * 0.22), (cx - 4, base - h * 0.22)]
    ic.fill(ic.poly_mask(cone), "#dcc29c", "#6e5038", (cx - w / 2, cx + w / 2), vertical=False, noise=0.18)
    ic.line([(cx - w * 0.3, base - h + 8), (cx - 3, base - h * 0.3)], 4, (255, 246, 226, 90))
    mouth = (cx - w / 2, base - h - 9, cx + w / 2, base - h + 9)
    ic.fill(ic.mask("ellipse", mouth), "#ece2cc", "#a89a80", radial=(cx - w * 0.3, base - h - 8, w), noise=0.12)
    ic.overlay(lambda d: d.ellipse(mouth, outline=(70, 52, 36, 180), width=3))
    ic.outline(cone[1:] + [cone[0]], 3, (60, 42, 28, 150))


def mill(ic: Icon, cx: float, top: float, base: float) -> tuple[float, float]:
    """Trapiche: three tall fluted rollers in a heavy frame over a juice tray, crown gears on top where
    the middle shaft rises to the sweep, a spout pouring juice into a pot. Returns the sweep pivot."""
    hw = 132
    # juice tray with its spout
    ic.poly([(cx - hw - 30, base - 44), (cx + hw + 30, base - 44), (cx + hw + 20, base), (cx - hw - 20, base)],
            "#8a6440", "#3e2a18", edge=4)
    ic.poly([(cx - hw - 16, base - 44), (cx + hw + 16, base - 44), (cx + hw + 6, base - 30), (cx - hw - 6, base - 30)],
            "#b09454", "#6e5022", edge=0)  # juice
    ic.shade(ic.mask("rectangle", (cx - hw - 16, base - 46, cx + hw + 16, base - 38)), (255, 240, 190), 0.3)
    sx = cx - 30
    ic.poly([(sx - 14, base - 12), (sx + 14, base - 12), (sx + 10, base + 12), (sx - 10, base + 12)], "#8a6440", "#3e2a18",
            edge=3)
    ic.fill(ic.mask("ellipse", (sx - 34, base + 28, sx + 34, base + 66)), "#b07a50", "#4a2a18",
            radial=(sx - 20, base + 30, 70), noise=0.2)  # clay pot catching the juice
    ic.fill(ic.mask("ellipse", (sx - 24, base + 26, sx + 24, base + 40)), "#2a1a10", "#4a3a20", (base + 26, base + 40))
    ic.overlay(lambda d: d.ellipse((sx - 26, base + 24, sx + 26, base + 42), outline=(170, 120, 80, 220), width=4))
    ic.line([(sx, base + 10), (sx + 1, base + 34)], 8, (214, 200, 128, 235))  # stream of pale juice
    ic.line([(sx - 1, base + 12), (sx - 1, base + 32)], 3, (250, 244, 200, 200))
    # rollers
    r = 28
    for k, dx in enumerate((-60, 0, 60)):
        roller(ic, cx + dx, top + 12, base - 46, r)
        if k < 2:  # the nip between two drums
            ic.shade(ic.mask("rectangle", (cx + dx + r - 4, top + 12, cx + dx + r + 6, base - 46)), alpha=0.55, blur=3)
    # posts and head beam, cane stalks being fed between the rollers
    for px in (cx - hw, cx + hw):
        timber(ic, (px, top - 40), (px, base - 30), 34)
    timber(ic, (cx - hw - 40, top - 10), (cx + hw + 40, top - 10), 40)
    ic.shade(ic.mask("rectangle", (cx - hw, top + 10, cx + hw, top + 50)), alpha=0.35, blur=10)
    for y in (top + 120, top + 140):  # cane fed into the first nip
        cut_cane(ic, (cx - hw - 70, y + 8), (cx - 32, y), 11, CUT[0])
    for y in (top + 130, top + 162):  # crushed bagasse coming out
        ic.poly([(cx + 34, y - 6), (cx + hw + 50, y + 4), (cx + hw + 56, y + 16), (cx + 34, y + 10)],
                "#c8b886", "#7a6a44", edge=3)
    # crown gears on the rollers above the beam, the middle one driven by the shaft
    for dx in (-60, 60):
        cog(ic, cx + dx, top - 40, 34, 10, 12, 12)
    cog(ic, cx, top - 46, 44, 13, 16, 14)
    ic.rect((cx - 16, top - 132, cx + 16, top - 44), "#8e6642", "#3e2a18", vertical=False, edge=4)
    ic.rect((cx - 22, top - 60, cx + 22, top - 48), "#6e6c68", "#2a2a2a", edge=3)
    return (cx, top - 108)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 0.86

    boiling_house(ic)
    # cane standing behind the mill, left
    m = stand(ic, 70, 430, 850, 890, 560, 620, 10)
    close_gaps(ic, ic.mask("ellipse", (-20, 160, 520, 1000)).filter(ImageFilter.GaussianBlur(30)), 17)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 700, SIZE, SIZE))), (10, 14, 4), 0.35, blur=30)

    # trodden yard, reaching up to the foot of the boiling-house wall
    top = [(20, 920)] + [(x, 866 + rnd.uniform(-6, 6)) for x in np.linspace(80, 960, 12)] + [(1008, 900)]
    ground = top + [(1010, 994), (520, 1004), (16, 996)]
    ic.poly(ground, "#86684a", "#56422e", noise=0.34, edge=3)
    for _ in range(40):
        x, y = rnd.uniform(40, 990), rnd.uniform(890, 994)
        ic.shade(ic.mask("ellipse", (x - 14, y - 6, x + 14, y + 6)), (255, 236, 200) if rnd.random() < 0.4 else (0, 0, 0),
                 0.16, blur=2)
    ic.shade(ic.mask("ellipse", (250, 900, 760, 980)), alpha=0.35, blur=14)

    pivot = mill(ic, 470, 660, 940)
    # clay sugar-loaf moulds by the boiling house
    ic.shade(ic.mask("ellipse", (930, 960, 1016, 1000)), alpha=0.4, blur=8)
    mould(ic, 994, 962, 84, 42)
    mould(ic, 964, 990, 92, 48)
    # the ox walking its round, the sweep from the shaft to its yoke
    ic.shade(ic.mask("ellipse", (600, 950, 950, 1000)), alpha=0.45, blur=10)
    yoke = ox(ic, 680, 740)
    timber(ic, pivot, yoke, 26)
    ic.rect((yoke[0] - 12, yoke[1] - 16, yoke[0] + 12, yoke[1] + 16), "#6e6c68", "#2a2a2a", edge=3)

    # cut cane waiting to be pressed, front left
    ic.shade(ic.mask("ellipse", (30, 950, 380, 1004)), alpha=0.45, blur=10)
    cane_bundle(ic, 60, 962, 250, 26, rows=3, tilt=6)
