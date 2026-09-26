"""Millet Rotation Farm: strips of millet, cowpeas and grazed fallow before a compound with granaries.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/millet_rotations/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/millet_rotations

Identity: the third tier shows the rotation itself. Three plots lie side by side, each in a
different turn: tall millet with drooping heads at the left, low dark-green cowpeas in the middle,
pale grazed fallow with dung heaps and a wattle fence at the right. The farmstead behind has grown
into a compound of a mud house and two raised granaries.

Local helpers: the millet helpers of ``millet_farm``, the building helpers of ``millet_farmstead``
(``mud``, ``cone``, ``granary``, ``jar``), plus ``pulse`` (a low cowpea clump), ``wattle`` (woven
stick fence) and ``dung`` (a manure heap).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 57
REFS = ("farming_village", "terraces", "fiber_crops_farm", "free_village")

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


MUD = ("#c89a64", "#86583a")
MUD_DARK = ("#9a5a3a", "#5a3020")


def mud(ic: Icon, m: Image.Image, c=MUD, span=None, vertical: bool = False, cracks: int = 5) -> None:
    """Plastered earth: warm gradient, hand-smoothed patches, a few hairline cracks, grime low down."""
    rnd = ic.random
    bb = m.getbbox()
    span = span or ((bb[0], bb[2]) if not vertical else (bb[1], bb[3]))
    ic.fill(m, c[0], c[1], span, vertical, noise=0.3, chroma=0.12)
    for _ in range(int((bb[2] - bb[0]) * (bb[3] - bb[1]) / 5000)):
        x, y = rnd.uniform(bb[0], bb[2]), rnd.uniform(bb[1], bb[3])
        r = rnd.uniform(14, 34)
        light = rnd.random() < 0.5
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6))),
                 (255, 232, 196) if light else (40, 20, 8), 0.12, blur=6)

    def crack(d):
        for _ in range(cracks):
            x, y = rnd.uniform(bb[0], bb[2]), rnd.uniform(bb[1], bb[3])
            pts = [(x, y)]
            for _ in range(3):
                x, y = x + rnd.uniform(-14, 14), y + rnd.uniform(8, 22)
                pts.append((x, y))
            d.line(pts, fill=(60, 34, 18, 110), width=3)

    ic.overlay(crack, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, bb[3] - (bb[3] - bb[1]) * 0.25, SIZE, SIZE))), (40, 24, 10),
             0.35, blur=20)


def cone(ic: Icon, cx: float, apex: float, eave: float, r: float, sag: float = 40,
         c=("#c4a86c", "#6a5230")) -> Image.Image:
    """Conical thatch hat seen from slightly above: straw strokes run from the apex to a ragged,
    curved eave; lit on the left. Returns its mask."""
    rnd = ic.random
    ts = np.linspace(0, 1, 40)
    lip = [(cx - r + 2 * r * t, eave + sag * math.sin(math.pi * t)) for t in ts]
    pts = [(cx - 8, apex), (cx + 8, apex)] + lip[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (cx - r * 0.9, cx + r), vertical=False, noise=0.3, chroma=0.12)

    def straw(d):
        for _ in range(900):
            t = rnd.random()
            ex, ey = lip[int(t * 39)]
            f = rnd.uniform(0.1, 1.0)
            x0, y0 = cx + (ex - cx) * f, apex + (ey - apex) * f
            L = rnd.uniform(0.08, 0.2)
            x1, y1 = x0 + (ex - cx) * L, y0 + (ey - apex) * L
            col = (238, 216, 150, 90) if rnd.random() < 0.5 - 0.3 * (t - 0.5) else (56, 40, 18, 90)
            d.line([(x0, y0), (x1, y1)], fill=col, width=3)

    ic.overlay(straw, m)
    # courses: faint rings that follow the eave curve
    for f in (0.35, 0.58, 0.8):
        ring = [(cx + (x - cx) * f, apex + (y - apex) * f) for x, y in lip]
        ic.line(ring, 5, (70, 50, 22, 110))
    ic.shade(ic.poly_mask([(cx + 10, apex)] + [p for p in lip if p[0] > cx + r * 0.1][::-1] + [(cx + r * 0.1, eave + sag)]),
             (30, 18, 6), 0.3, blur=18)
    ragged = lip + [(x + rnd.uniform(-4, 4), y + 22 + rnd.uniform(-4, 6)) for x, y in lip[::-1]]
    ic.fill(ic.poly_mask(ragged), "#8e7442", "#4c3a1c", (eave, eave + sag + 30), noise=0.35)

    def cut(d):
        for x, y in lip[::1]:
            for k in range(3):
                xx = x + k * 5
                d.line([(xx, y + 2), (xx + rnd.uniform(-3, 3), y + 22)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(ragged))
    # a bound straw knot at the apex
    ic.poly([(cx - 16, apex + 20), (cx - 6, apex - 26), (cx + 8, apex - 28), (cx + 16, apex + 20)], "#a88a52", "#5a4424",
            edge=3)
    ic.line([(cx - 16, apex + 8), (cx + 16, apex + 8)], 6, (70, 50, 26))
    return m


def granary(ic: Icon, cx: float, r: float, body_top: float, body_bot: float, legs_bot: float) -> None:
    """Round mud granary raised on forked posts over flat stones, a sealed hatch, conical thatch hat."""
    rnd = ic.random
    top = body_bot - 10
    # the dark space under the store, then posts: the back ones thinner and in shadow
    ic.fill(ic.poly_mask([(cx - r * 0.95, top), (cx + r * 0.95, top), (cx + r * 0.8, legs_bot - 20),
                          (cx - r * 0.8, legs_bot - 20)]), "#2e2014", "#1a120a", noise=0.2)
    for dx, dark in ((-0.4, True), (0.45, True), (-0.82, False), (0.02, False), (0.8, False)):
        x = cx + r * dx + rnd.uniform(-6, 6)
        w = 22 if dark else 30
        lean = rnd.uniform(-8, 8)
        ic.line([(x, top), (x + lean, legs_bot - 6)], w + 8, (40, 26, 14))
        ic.line([(x - 2, top), (x + lean - 2, legs_bot - 6)], w, (96, 70, 44) if dark else (134, 98, 62))
        if not dark:
            ic.line([(x - w * 0.3, top + 10), (x + lean - w * 0.3, legs_bot - 16)], 5, (196, 160, 112, 120))
            # fork at the top holding the platform
            ic.line([(x, top + 30), (x - 26, top - 6)], 14, (110, 80, 50))
            ic.line([(x, top + 30), (x + 26, top - 6)], 14, (110, 80, 50))
            stone = ic.jitter(x + lean, legs_bot - 4, w * 1.4, 16, 9, 0.12)
            ic.poly(stone, "#8a7e6c", "#4a4236", noise=0.25, edge=4)
    ic.shade(ic.mask("rectangle", (cx - r, body_bot - 10, cx + r, body_bot + 40)), alpha=0.5, blur=10)
    # platform of logs
    ic.poly([(cx - r * 1.08, body_bot - 16), (cx + r * 1.08, body_bot - 16), (cx + r * 1.02, body_bot + 12),
             (cx - r * 1.02, body_bot + 12)], "#7a5a38", "#3e2a18", edge=4)
    for x in np.arange(cx - r, cx + r, 26):
        ic.ellipse((x, body_bot - 12, x + 22, body_bot + 8), "#9a7650", "#5a4028", edge=2)
    # the store: a slightly bulging mud cylinder with a rounded bottom
    ts = np.linspace(0, 1, 30)
    left = [(cx - r - r * 0.06 * math.sin(math.pi * t), body_top + (body_bot - body_top) * t) for t in ts]
    right = [(cx + r + r * 0.06 * math.sin(math.pi * t), body_bot - (body_bot - body_top) * t) for t in ts]
    bottom = [(cx - r + 2 * r * t, body_bot + 10 * math.sin(math.pi * t)) for t in ts]
    body = left + bottom + right
    m = ic.poly_mask(body)
    mud(ic, m, MUD, (cx - r * 1.2, cx + r * 1.1))
    # roundness: highlight band on the left third, core shadow on the right
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx - r * 0.75, 0, cx - r * 0.35, SIZE))), (255, 236, 200), 0.18, blur=24)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (cx + r * 0.35, 0, SIZE, SIZE))), (30, 14, 4), 0.35, blur=30)
    # a coil ridge where the mud was built up course by course
    for y in np.linspace(body_top + 50, body_bot - 30, 4):
        ic.line([(cx - r * 1.02, y), (cx, y + 8), (cx + r * 1.02, y)], 4, (80, 46, 24, 90))
    # sealed hatch high on the front
    hx, hy = cx - r * 0.1, body_top + 60
    ic.fill(ic.mask("ellipse", (hx - 34, hy - 30, hx + 34, hy + 34)), "#6e4428", "#3a2212")
    ic.fill(ic.mask("ellipse", (hx - 24, hy - 20, hx + 24, hy + 24)), "#a07048", "#5e3a20", radial=(hx - 20, hy - 20, 50))
    ic.overlay(lambda d: d.ellipse((hx - 34, hy - 30, hx + 34, hy + 34), outline=(40, 24, 12, 180), width=4))
    ic.outline(body, 4, (46, 28, 14, 170))


def jar(ic: Icon, cx: float, base: float, w: float, h: float, c=("#b8704a", "#5a2e18")) -> None:
    """Sealed clay jar: round body, short neck, a domed mud seal on the mouth."""
    body = ic.mask("ellipse", (cx - w / 2, base - h * 0.86, cx + w / 2, base))
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.3, base - h * 0.8, w * 1.05), noise=0.22)
    ic.overlay(lambda d: d.ellipse((cx - w / 2, base - h * 0.86, cx + w / 2, base), outline=(50, 24, 12, 170), width=4))
    ic.shade(ic.mask("ellipse", (cx - w * 0.34, base - h * 0.74, cx - w * 0.12, base - h * 0.44)), (255, 226, 190), 0.3,
             blur=6)
    # a painted band
    ic.line([(cx - w * 0.47, base - h * 0.55), (cx, base - h * 0.5), (cx + w * 0.47, base - h * 0.55)], 5,
            (70, 32, 16, 150))
    nw = w * 0.36
    ic.rect((cx - nw / 2, base - h * 0.96, cx + nw / 2, base - h * 0.8), c[0], c[1], vertical=False, edge=4)
    ic.fill(ic.mask("ellipse", (cx - nw * 0.62, base - h * 1.08, cx + nw * 0.62, base - h * 0.9)), "#8a6a48", "#4a3420",
            radial=(cx - nw * 0.4, base - h * 1.08, nw))
    ic.overlay(lambda d: d.ellipse((cx - nw * 0.62, base - h * 1.08, cx + nw * 0.62, base - h * 0.9),
                                   outline=(40, 26, 12, 170), width=3))


PULSE = ("#5e8034", "#1c300c")


def pulse(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Low cowpea clump: a dark mound of round trifoliate leaves, a few pale flowers and pods."""
    rnd = ic.random
    ic.fill(ic.poly_mask(ic.jitter(cx, base - h * 0.4, w * 0.45, h * 0.42, 14, 0.1)), "#2e4818", "#14220a", noise=0.3)
    leaves = []
    for _ in range(16):
        a = rnd.uniform(math.pi, 2 * math.pi)
        rr = rnd.random() ** 0.5
        x, y = cx + math.cos(a) * w * 0.45 * rr, base - h * 0.35 + math.sin(a) * h * 0.55 * rr
        leaves.append((y, x))
    lit, mid, dk = (124, 158, 70), (84, 118, 44), (30, 50, 14)

    def leaflets(d):  # three leaflets per leaf: dark rim, body, lit upper-left side
        for y, x in sorted(leaves):
            f = 0.8 + 0.4 * (y - (base - h)) / h
            for off in (-1, 0, 1):
                lx, ly = x + off * w * 0.09, y - (w * 0.05 if off == 0 else 0)
                rx, ry = w * 0.1, w * 0.075
                d.ellipse((lx - rx, ly - ry, lx + rx, ly + ry), fill=dk + (255,))
                d.ellipse((lx - rx + 2, ly - ry + 2, lx + rx - 3, ly + ry - 3),
                          fill=tuple(int(v * rnd.uniform(0.85, 1.1) / f) for v in mid) + (255,))
                d.ellipse((lx - rx * 0.8, ly - ry * 0.8, lx + rx * 0.1, ly + ry * 0.05), fill=lit + (150,))

    ic.overlay(leaflets)
    for _ in range(3):
        x, y = cx + rnd.uniform(-w * 0.35, w * 0.35), base - h * rnd.uniform(0.3, 0.8)
        if rnd.random() < 0.5:
            ic.fill(ic.mask("ellipse", (x - 6, y - 5, x + 6, y + 5)), "#c8b0c8", "#806078", radial=(x - 4, y - 4, 12))
        else:
            ic.line([(x, y), (x + rnd.uniform(-30, 30), y + 26)], 6, (150, 150, 80))
    ic.shade(ic.mask("ellipse", (cx - w * 0.5, base - 10, cx + w * 0.5, base + 12)), alpha=0.4, blur=6)


def wattle(ic: Icon, pts, h: float = 70) -> None:
    """Low fence of stakes with sticks woven between them, following the ground line ``pts``."""
    rnd = ic.random
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    stakes = np.arange(min(xs), max(xs) + 1, 64)
    band = [(x, np.interp(x, xs, ys) - h) for x in stakes] + [(x, np.interp(x, xs, ys)) for x in stakes[::-1]]
    m = ic.poly_mask(band)
    ic.fill(m, "#6a4e30", "#34220e", noise=0.3)

    def weave(d):
        n = max(int(h / 11), 6)
        for k in range(n):
            f = (k + 0.5) / n
            line = [(x, np.interp(x, xs, ys) - h * f + (4 if (i + k) % 2 else -4)) for i, x in enumerate(stakes)]
            d.line(line, fill=(150, 116, 74, 170) if k % 2 else (44, 28, 12, 180), width=7)

    ic.overlay(weave, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, min(ys) - h * 0.35, SIZE, SIZE))), (30, 18, 6), 0.35, blur=10)
    for x in stakes:
        y = np.interp(x, xs, ys)
        ic.line([(x, y + 4), (x + rnd.uniform(-3, 3), y - h - 18)], 16, (40, 26, 12))
        ic.line([(x - 2, y + 2), (x - 2, y - h - 16)], 9, (112, 82, 50))
    ic.outline(band, 3, (40, 26, 12, 150))


def dung(ic: Icon, cx: float, base: float, w: float) -> None:
    """Manure heap on the fallow: dark lumpy dome with straw bits and a lit upper-left flank."""
    rnd = ic.random
    h = w * 0.42
    ts = np.linspace(0, 1, 18)
    pts = [(cx - w / 2 + w * t, base - h * math.sin(math.pi * t) ** 0.8 * rnd.uniform(0.9, 1.08)) for t in ts]
    pts += [(cx + w / 2, base + 4), (cx - w / 2, base + 4)]
    ic.shade(ic.mask("ellipse", (cx - w * 0.62, base - 10, cx + w * 0.7, base + 16)), alpha=0.45, blur=6)
    m = ic.poly_mask(pts)
    ic.fill(m, "#5e4228", "#1a100a", radial=(cx - w * 0.3, base - h, w * 0.95), noise=0.35)

    def straw(d):
        for _ in range(int(w * 0.5)):
            x, y = rnd.uniform(cx - w / 2, cx + w / 2), rnd.uniform(base - h, base)
            L = rnd.uniform(6, 14)
            a = rnd.uniform(0, math.pi)
            d.line([(x, y), (x + math.cos(a) * L, y - math.sin(a) * L)], fill=(206, 184, 120, 130), width=2)

    ic.overlay(straw, m)
    ic.outline(pts, 3, (30, 20, 10, 150))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.72
    ic.grade["mute"] = 0.84

    # ---- compound at the back right: two granaries flanking a mud house
    H0, H1, EAVE, BASE = 560, 850, 420, 580
    mud(ic, ic.mask("rectangle", (H0, EAVE, H1, BASE)), MUD_DARK, (H0, H1))
    ic.rect((700, 490, 756, BASE), "#2e1c12", "#140c08", edge=4)
    ic.rect((790, 470, 826, 510), "#2a1a10", "#120a06", edge=3)
    ic.shade(ic.mask("rectangle", (H0, EAVE, H1, EAVE + 40)), alpha=0.5, blur=10)
    ic.outline([(H0, EAVE), (H1, EAVE), (H1, BASE), (H0, BASE)], 4)
    thatch_cap(ic, [(H0 - 30, EAVE + 18), (640, 300), (780, 296), (H1 + 30, EAVE + 20), (H1 + 24, EAVE + 36),
                    (H0 - 24, EAVE + 34)], strokes=800)
    for gx, top in ((930, 250), (470, 262)):
        granary(ic, gx, 72, top + 150, top + 270, top + 340)
        cone(ic, gx + 2, top - 10, top + 140, 72 * 1.6, sag=24)
        ic.shade(ic.mask("rectangle", (gx - 90, top + 150, gx + 90, top + 190)), (20, 10, 4), 0.4, blur=10)

    # ---- the fields: one ground, three plots side by side, each in a different turn
    ground = [(20, 960), (40, 640)] + [(x, 604 + rnd.uniform(-8, 8)) for x in np.linspace(90, 940, 10)] + [(996, 620),
                                                                                                       (1008, 990)]
    soil(ic, ground + [(520, 1008), (40, 1000)], clods=50)
    B1 = [(372, 606), (340, 1004)]  # millet | cowpeas
    B2 = [(680, 608), (700, 1006)]  # cowpeas | fallow

    # fallow plot, right: pale grazed grass, dung heaps, a wattle fence along its back
    fal = [B2[0], (996, 620), (1008, 990), B2[1]]
    fm = ic.poly_mask(fal)
    ic.fill(fm, "#a89464", "#6a5634", (606, 1000), noise=0.34)
    # hoof-trodden patches of bare earth where the herd stood and walked
    for _ in range(26):
        x, y = rnd.uniform(700, 1000), rnd.uniform(640, 990)
        r = rnd.uniform(18, 44) * (0.6 + 0.6 * (y - 600) / 400)
        ic.shade(ic.intersect(fm, ic.mask("ellipse", (x - r * 1.5, y - r * 0.5, x + r * 1.5, y + r * 0.5))),
                 (70, 44, 22), 0.4, blur=5)

    def tufts(d):  # clumps of dry grass: a fan of blades over a dark root
        for _ in range(170):
            x, y = rnd.uniform(690, 1008), rnd.uniform(630, 1004)
            s = 0.6 + 0.7 * (y - 600) / 400
            d.ellipse((x - 12 * s, y - 4 * s, x + 12 * s, y + 4 * s), fill=(58, 42, 18, 120))
            for _ in range(6):
                a = rnd.uniform(-2.4, -0.7)
                L = rnd.uniform(14, 30) * s
                col = (214, 196, 128, 150) if rnd.random() < 0.5 else (108, 88, 40, 150)
                d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(tufts, fm)
    wattle(ic, [(684, 646), (1004, 652)], 118)
    for x, y, w in ((800, 770, 150), (820, 935, 180)):
        dung(ic, x, y, w)

    # cowpea plot, middle: rows of low dark clumps on darker earth
    pm = ic.poly_mask([B1[0], B2[0], B2[1], B1[1]])
    ic.fill(pm, "#6e4e30", "#4e3420", (606, 1004), noise=0.3)
    for row, y in enumerate(np.linspace(660, 960, 6)):
        s = 0.7 + 0.5 * (y - 660) / 300
        x0 = np.interp(y, (606, 1004), (B1[0][0], B1[1][0])) + 40 * s
        x1 = np.interp(y, (606, 1004), (B2[0][0], B2[1][0])) - 30 * s
        n = max(int((x1 - x0) / (78 * s)), 2)
        for x in np.linspace(x0, x1, n):
            pulse(ic, x + rnd.uniform(-8, 8), y + rnd.uniform(-4, 4), 130 * s, 76 * s)

    # millet plot, left: a dense stand of tall millet from the soil up to the heads
    body = [(30, 992), (22, 820), (36, 680), (26, 560)] + [
        (x, 470 + rnd.uniform(-30, 30)) for x in np.linspace(50, 330, 8)] + [(356, 520), (360, 606), (340, 1000)]
    bm = ic.poly_mask(body)
    ic.fill(bm, "#76783c", "#303416", (470, 1000), noise=0.3, chroma=0.12)

    def thicket(d):  # stalks and blades of the plants deeper in the plot
        for _ in range(170):
            x, y = rnd.uniform(24, 360), rnd.uniform(520, 990)
            L = rnd.uniform(50, 130)
            col = (156, 156, 88, 120) if rnd.random() < 0.45 else (26, 32, 10, 130)
            d.line([(x, y), (x + rnd.uniform(-14, 14), y - L)], fill=col, width=rnd.choice((3, 4, 5)))
        for _ in range(70):
            x, y = rnd.uniform(24, 360), rnd.uniform(480, 960)
            a = rnd.choice((-1, 1))
            d.line([(x, y), (x + a * rnd.uniform(24, 50), y - rnd.uniform(6, 20)), (x + a * rnd.uniform(50, 80),
                    y + rnd.uniform(0, 16))], fill=(136, 146, 74, 120), width=5)

    ic.overlay(thicket, bm)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, 900, SIZE, SIZE))), (40, 26, 10), 0.35, blur=16)
    stand(ic, [(700, 300, 62)], 40, 350, dry=0.45, hs=1.2, vary=(0.8, 1.15), sw=0.75, lw=0.75, leaves=4)
    ic.shade(bm, (20, 26, 8), 0.2, blur=20)
    stand(ic, [(840, 380, 76)], 40, 340, dry=0.4, hs=1.2, vary=(0.8, 1.15), sw=0.75, lw=0.75, leaves=4)
    for x, side, h in ((70, 1, 480), (200, -1, 440), (320, 1, 420)):
        millet(ic, x + rnd.uniform(-8, 8), 986, h, side=side, lean=rnd.uniform(-20, 20), dry=0.35, hs=1.2, leaves=4,
               sw=0.75, lw=0.75)

    # a sealed jar of seed at the bottom right, by the fallow
    ic.shade(ic.mask("ellipse", (870, 970, 1016, 1008)), alpha=0.5, blur=8)
    jar(ic, 950, 1000, 110, 130)
