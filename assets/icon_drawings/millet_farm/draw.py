"""Millet Farm: an open field of tall millet with heavy drooping seed heads, a basket of cut heads.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/millet_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/millet_farm

Identity: the first tier is only the field. A stand of tall millet on dry red-brown soil, each
stalk bent over by a thick, bushy golden seed head; a hand hoe and a woven basket heaped with cut
heads sit at the bottom right.

Local helpers (shared by the millet tiers): ``blade`` (long arching strap leaf), ``head`` (thick
bushy seed head hanging from a bending neck), ``millet`` (one plant: stalk, leaves, drooping head),
``stand`` (rows of plants in perspective), ``soil`` (dry field strip with clods), ``hoe``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("farming_village", "fiber_crops_farm", "terraces", "sugar_plantation")

HEADS = (("#dca238", "#6a3e0e"), ("#d69c36", "#5e380a"), ("#e8b64a", "#704612"), ("#cc9430", "#58340a"))
BLADE = ("#788a3e", "#222e0c")
BLADE_DRY = ("#a8904e", "#554016")


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def mix(a, b, t: float) -> tuple:
    a, b = rgb(a), rgb(b)
    t = min(max(t, 0.0), 1.0)
    return tuple(int(v) for v in a * (1 - t) + b * t)


def blade(ic: Icon, base, deg: float, length: float, width: float, droop: float = 0.7, colors=BLADE) -> None:
    """Long strap leaf of a millet plant: rises from ``base`` towards ``deg`` and arches over."""
    a = math.radians(deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 22)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * min(1.0, 0.35 + t * 5) * (1 - t ** 1.5) for t in ts]
    s1 = [p + n * w for p, w in zip(spine, hw)]
    s2 = [p - n * w for p, w in zip(spine, hw)]
    pts = [tuple(p) for p in s1 + s2[::-1]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1], radial=(min(xs), min(ys), length * 1.1), noise=0.2, chroma=0.14)
    lower = s1 if n[1] > 0 else s2
    ic.shade(ic.poly_mask([tuple(p) for p in spine] + [tuple(p) for p in lower[::-1]]), (8, 14, 4), 0.32)
    ic.line([tuple(p) for p in spine[1:-5]], 3, (214, 214, 160, 80))
    ic.outline(pts, 3, (22, 30, 10, 120))


def head(ic: Icon, p0, a0: float, turn: float, length: float, width: float, colors, neck: float = 0.22,
         bend: float = 0.4) -> Image.Image:
    """Thick bushy millet head along a bending spine from ``p0``: starts towards ``a0`` degrees and
    turns by ``turn`` degrees over its length (0 = right, 90 = down); ``bend`` < 1 turns early so the
    head hangs. A bare neck of stem comes first. Returns the head mask."""
    rnd = ic.random
    n = 34
    p = np.array(p0, float)
    spine = [p.copy()]
    for k in range(1, n + 1):
        a = math.radians(a0 + turn * (k / n) ** bend)
        p = p + length / n * np.array([math.cos(a), math.sin(a)])
        spine.append(p.copy())
    k0 = int(n * neck)
    if k0:
        ic.line([tuple(q) for q in spine[: k0 + 2]], max(int(width * 0.2), 6), (58, 56, 24))
        ic.line([tuple(q) for q in spine[: k0 + 2]], max(int(width * 0.12), 4), (150, 140, 76))
    body = spine[k0:]
    m = blank()
    dr = ImageDraw.Draw(m)
    rads = []
    wob = 1.0
    for i, q in enumerate(body):
        u = 0.05 + 0.92 * i / (len(body) - 1)
        wob = 0.7 * wob + 0.3 * rnd.uniform(0.8, 1.2)
        r = width / 2 * max(math.sin(math.pi * u ** 0.62) ** 0.55, 0.2) * wob
        rads.append(r)
        dr.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=255)
    bb = m.getbbox()
    ic.fill(m, colors[0], colors[1], radial=(bb[0] + (bb[2] - bb[0]) * 0.2, bb[1], max(bb[2] - bb[0], bb[3] - bb[1]) * 1.1),
            noise=0.3, chroma=0.12)
    lit = tuple(min(255, int(v * 1.25)) for v in rgb(colors[0]))
    dk = tuple(int(v * 0.55) for v in rgb(colors[1]))

    def grains(d):
        for q, r in zip(body, rads):
            for _ in range(int(r * 1.2)):
                a = rnd.uniform(0, 2 * math.pi)
                rr = r * rnd.random() ** 0.6
                x, y = q[0] + math.cos(a) * rr, q[1] + math.sin(a) * rr
                g = rnd.uniform(2.0, 3.4) * (width / 60) ** 0.5
                if math.cos(a) + math.sin(a) < rnd.uniform(-0.6, 0.4):
                    d.ellipse((x - g, y - g, x + g, y + g), fill=lit + (95,))
                else:
                    d.ellipse((x - g, y - g, x + g, y + g), fill=dk + (80,))

    ic.overlay(grains, m)
    k = max(int(width * 0.14), 3)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, -k, -k)), (30, 16, 4), 0.45, blur=3)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, k, k)), (255, 236, 180), 0.22, blur=2)

    def bristles(d):  # fine awns breaking the rim, so the head reads bushy
        for q, r in zip(body, rads):
            for _ in range(3):
                a = rnd.uniform(0, 2 * math.pi)
                x0, y0 = q[0] + math.cos(a) * r * 0.7, q[1] + math.sin(a) * r * 0.7
                L = r * rnd.uniform(0.3, 0.5)
                col = dk + (120,) if rnd.random() < 0.55 else lit + (110,)
                d.line([(x0, y0), (x0 + math.cos(a) * L, y0 + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(bristles)
    return m


def millet(ic: Icon, x: float, base: float, h: float, side: int | None = None, lean: float = 0,
           colors=None, dry: float = 0.3, leaves: int = 6, hs: float = 1.0, sw: float = 1.0, lw: float = 1.0) -> None:
    """One millet plant: stalk, arching strap leaves, a thick seed head hanging to ``side``.
    ``sw`` and ``lw`` scale the stalk and leaf width."""
    rnd = ic.random
    side = side or rnd.choice((-1, 1))
    colors = colors or rnd.choice(HEADS)
    top = np.array((x + lean, base - h))
    bot = np.array((x, base))

    def at(t):
        return bot + (top - bot) * t + np.array([lean * 0.25 * math.sin(math.pi * t), 0])

    specs = []
    for i in range(leaves):
        t = 0.08 + 0.64 * i / max(leaves - 1, 1) + rnd.uniform(-0.03, 0.03)
        s = 1 if (i + (side > 0)) % 2 else -1
        up = rnd.uniform(20, 55)
        L = h * rnd.uniform(0.42, 0.55) * (1.05 - 0.4 * t)
        cols = tuple(mix(a, b, dry + (0.55 - t) * 0.9 + rnd.uniform(-0.15, 0.2)) for a, b in zip(BLADE, BLADE_DRY))
        specs.append((t, s, up, L, cols))
    wid = h * 0.068 * lw
    for k, (t, s, up, L, cols) in enumerate(specs):
        if k % 3 == 0:
            blade(ic, tuple(at(t)), (-up if s > 0 else 180 + up), L, wid, rnd.uniform(0.55, 0.9), cols)
    pts = [tuple(at(t)) for t in np.linspace(0, 1, 10)]
    w = max(int(h * 0.022 * sw), 4)
    ic.line(pts, w + 4, (34, 34, 14))
    ic.line(pts, w, mix((70, 84, 36), (118, 100, 56), dry))
    ic.line([(p[0] - w * 0.25, p[1]) for p in pts], max(w // 3, 2), (196, 190, 130, 40))
    for k, (t, s, up, L, cols) in enumerate(specs):
        if k % 3:
            blade(ic, tuple(at(t)), (-up if s > 0 else 180 + up), L, wid, rnd.uniform(0.55, 0.9), cols)
    head(ic, tuple(top), -90 + side * rnd.uniform(0, 12), side * rnd.uniform(175, 195), h * hs * rnd.uniform(0.48, 0.54),
         h * hs * rnd.uniform(0.12, 0.135), colors)


def stand(ic: Icon, rows, x0: float, x1: float, dry: float = 0.3, gap: tuple | None = None, hs: float = 1.0,
          vary=(0.88, 1.1), **kw) -> None:
    """Rows of millet in perspective: rows = [(base_y, height, spacing), ...] from back to front.

    Each row shades the one behind it. ``gap`` = (x0, x1, row index from) leaves room for props;
    ``vary`` is the height range per plant, ``kw`` goes to ``millet``."""
    rnd = ic.random
    for ri, (base, h, step) in enumerate(rows):
        if ri:
            ic.shade(ic.mask("rectangle", (0, base - h * 0.6, SIZE, base + 10)), (14, 18, 4), 0.3, blur=30)
        xs = list(np.arange(x0 + rnd.uniform(0, step * 0.5), x1, step))
        rnd.shuffle(xs)
        for x in xs:
            if gap and ri >= gap[2] and gap[0] < x < gap[1]:
                continue
            millet(ic, x + rnd.uniform(-step * 0.3, step * 0.3), base + rnd.uniform(-6, 6), h * rnd.uniform(*vary),
                   lean=rnd.uniform(-h * 0.1, h * 0.1), dry=dry, hs=hs, **kw)


def soil(ic: Icon, pts, c=("#96643c", "#5a3a20"), clods: int = 60) -> None:
    """Dry red-brown field soil with light and dark clods."""
    rnd = ic.random
    ic.poly(pts, c[0], c[1], noise=0.32, edge=3)
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    for _ in range(clods):
        x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
        r = rnd.uniform(6, 14)
        light = rnd.random() < 0.45
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6))),
                 (255, 226, 180) if light else (30, 16, 6), 0.2, blur=2)


def hoe(ic: Icon, grip, blade_at) -> None:
    """Short-handled hand hoe lying on the ground: wooden haft, broad iron blade turned down."""
    ic.line([grip, blade_at], 20, (50, 32, 18))
    ic.line([grip, blade_at], 13, (150, 108, 66))
    ic.line([(grip[0] - 2, grip[1] - 3), (blade_at[0] - 2, blade_at[1] - 3)], 4, (206, 170, 120, 150))
    bx, by = blade_at
    pts = [(bx - 8, by - 14), (bx + 14, by - 8), (bx + 30, by + 46), (bx - 34, by + 52), (bx - 22, by + 6)]
    ic.poly(pts, "#8a8680", "#3e3a36", noise=0.25, edge=4)
    ic.shade(ic.poly_mask([(bx - 8, by - 14), (bx + 14, by - 8), (bx + 4, by + 20), (bx - 20, by + 8)]),
             (240, 236, 226), 0.25)


def thatch_cap(ic: Icon, pts, c=("#b8a06a", "#6c5632"), strokes: int = 500) -> None:
    """Small thatched roof plane: straw gradient, strokes down the slope, a ragged dark eave."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.32, chroma=0.12)

    def straw(d):
        for _ in range(strokes):
            x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
            L = rnd.uniform(12, 30)
            col = (236, 214, 150, 90) if rnd.random() < 0.5 else (60, 42, 20, 90)
            d.line([(x, y), (x + rnd.uniform(-5, 5), y + L)], fill=col, width=3)

    ic.overlay(straw, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, max(ys) - 22, SIZE, SIZE))), (40, 26, 10), 0.4, blur=4)
    ic.outline(pts, 4, (40, 28, 14, 170))


def watch_platform(ic: Icon, x0: float, x1: float, deck: float, ground: float) -> None:
    """Bird-scaring platform over the field: four rough poles, a lashed stick deck, a thatched sun cap."""
    rnd = ic.random
    w = x1 - x0
    for x in (x0 + w * 0.12, x1 - w * 0.08):  # back poles, thinner and darker
        ic.line([(x, deck - 190), (x + rnd.uniform(-6, 6), ground - 60)], 14, (54, 38, 22))
    # deck: lashed sticks seen from slightly above, then its front edge
    top = [(x0 + 6, deck - 40), (x1 - 6, deck - 40), (x1 + 12, deck), (x0 - 12, deck)]
    ic.poly(top, "#a8845a", "#7a5a38", edge=4)
    for y in np.arange(deck - 36, deck, 9):
        ic.line([(x0 - 8, y + rnd.uniform(-1, 1)), (x1 + 8, y + rnd.uniform(-1, 1))], 3, (60, 40, 20, 120))
    ic.shade(ic.poly_mask(top), (255, 240, 200), 0.15)
    ic.poly([(x0 - 12, deck), (x1 + 12, deck), (x1 + 4, deck + 26), (x0 - 4, deck + 26)], "#7a5a38", "#3e2a18", edge=4)
    for x in np.arange(x0, x1, 18):
        ic.line([(x + rnd.uniform(-2, 2), deck + 2), (x + rnd.uniform(-3, 3), deck + 24)], 3, (40, 26, 12, 150))
    for x, lean in ((x0 + 4, -10), (x1 - 4, 12)):  # front poles
        ic.line([(x, deck - 200), (x + lean, ground)], 22, (46, 30, 16))
        ic.line([(x - 2, deck - 200), (x + lean - 2, ground)], 14, (132, 96, 60))
        ic.line([(x - 5, deck - 200), (x + lean - 5, ground)], 4, (190, 156, 110, 130))
    for x in (x0 + 4, x1 - 4):  # lashings
        ic.line([(x - 14, deck + 6), (x + 14, deck + 16)], 6, (70, 52, 30))
    ic.line([(x0 - 6, deck - 100), (x1 + 6, deck - 104)], 10, (92, 66, 40))  # rail
    # a clay pot and a sling stone heap for scaring birds
    ic.fill(ic.mask("ellipse", (x0 + 40, deck - 76, x0 + 96, deck - 24)), "#b06a3e", "#5a2e16", radial=(x0 + 50, deck - 76, 70))
    ic.fill(ic.mask("ellipse", (x0 + 50, deck - 82, x0 + 86, deck - 70)), "#3a2012", "#2a160c")
    thatch_cap(ic, [(x0 - 60, deck - 170), (x0 + w * 0.3, deck - 270), (x1 - w * 0.25, deck - 276),
                    (x1 + 60, deck - 174), (x1 + 50, deck - 156), (x0 - 50, deck - 150)])
    ic.shade(ic.mask("rectangle", (x0, deck - 150, x1, deck - 90)), alpha=0.4, blur=12)
    # ladder leaning against the front
    for dx in (0, 46):
        ic.line([(x0 - 60 + dx, ground - 10), (x0 + 10 + dx, deck - 10)], 12, (46, 30, 16))
        ic.line([(x0 - 60 + dx, ground - 10), (x0 + 10 + dx, deck - 10)], 7, (140, 104, 66))
    for t in np.linspace(0.08, 0.92, 7):
        y = ground - 10 + (deck - ground) * t
        x = x0 - 60 + 70 * t
        ic.line([(x, y), (x + 46, y)], 8, (112, 80, 48))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.72
    ic.grade["mute"] = 0.84

    # dry field soil: the front strip shows below and between the stalks
    top = [(90, 930), (110, 890)] + [(x, 872 + rnd.uniform(-12, 10)) for x in np.linspace(130, 930, 10)] + [(990, 884)]
    soil(ic, top + [(1010, 996), (520, 1008), (96, 998)])
    # the far field as one shadowed olive mass of crop; the left side slopes and frays instead of a cut
    mass = [(165, 890), (118, 836), (150, 790), (104, 720), (146, 676), (112, 630), (150, 596)] + [
        (x, 540 + 50 * ((x - 540) / 440) ** 2 + rnd.uniform(-30, 30)) for x in np.linspace(170, 970, 14)
    ] + [(996, 660), (975, 890)]
    mass += [(x, 884 + rnd.uniform(-16, 8)) for x in np.linspace(930, 170, 12)]
    ic.poly(mass, "#6e6e38", "#2e3014", noise=0.3, edge=0)
    mm = ic.poly_mask(mass)

    def thicket(d):  # the stalks and blades of the plants further back, so the mass is not a wall
        for _ in range(260):
            x, y = rnd.uniform(130, 990), rnd.uniform(560, 900)
            L = rnd.uniform(40, 120)
            dx = rnd.uniform(-14, 14)
            col = (150, 150, 84, 120) if rnd.random() < 0.45 else (24, 30, 10, 130)
            d.line([(x, y), (x + dx, y - L)], fill=col, width=rnd.choice((3, 4, 5)))
        for _ in range(90):
            x, y = rnd.uniform(130, 990), rnd.uniform(560, 880)
            a = rnd.choice((-1, 1))
            d.line([(x, y), (x + a * rnd.uniform(24, 50), y - rnd.uniform(6, 20)), (x + a * rnd.uniform(50, 80),
                    y + rnd.uniform(0, 16))], fill=(130, 138, 70, 110), width=5)

    ic.overlay(thicket, mm)
    stand(ic, [(560, 200, 50)], 150, 600, dry=0.55, hs=1.25, vary=(0.7, 1.25), sw=0.7, lw=0.7, leaves=4)
    watch_platform(ic, 590, 830, 300, 830)
    stand(ic, [(600, 220, 58)], 800, 990, dry=0.55, hs=1.25, vary=(0.7, 1.2), sw=0.7, lw=0.7, leaves=4)
    stand(ic, [(730, 320, 90)], 170, 1000, dry=0.45, hs=1.25, vary=(0.72, 1.25), sw=0.7, lw=0.7, leaves=4)
    # dark olive shadow deep between the stalks, stopping short of the soil at the bottom
    ic.shade(ic.mask("rectangle", (0, 600, SIZE, 880)), (22, 28, 8), 0.38, blur=40)
    # front plants: thin stalks at irregular spacing and heights, a few leaning; the two at the left
    # hang their heads out past the edge of the field
    for x, side, h, lean in ((175, -1, 520, -45), (228, -1, 610, -30), (300, 1, 450, 14), (352, -1, 640, 30),
                             (462, 1, 520, -26), (528, 1, 410, 44), (610, -1, 580, -8), (676, 1, 470, 36)):
        millet(ic, x + rnd.uniform(-6, 6), 978 + rnd.uniform(-10, 6), h, side=side, lean=lean, dry=0.3,
               hs=1.15, leaves=3, sw=0.62, lw=0.62)

    # harvest corner: a basket heaped with cut heads and a hand hoe
    ic.shade(ic.mask("ellipse", (640, 950, 1016, 1008)), alpha=0.5, blur=10)
    hoe(ic, (650, 984), (780, 930))
    ic.fill(ic.mask("ellipse", (790, 846, 996, 900)), "#4a3016", "#2a1a0a")
    for cx, cy, deg in ((812, 872, -12), (840, 850, -4), (900, 858, 186), (960, 874, 196), (870, 878, 8)):
        head(ic, (cx, cy), deg, rnd.uniform(-12, 12), rnd.uniform(130, 150), rnd.uniform(38, 44), rnd.choice(HEADS),
             neck=0.0, bend=1.0)
    ic.basket(786, 876, 1000, 998, ("#b89058", "#6a4a28"))
