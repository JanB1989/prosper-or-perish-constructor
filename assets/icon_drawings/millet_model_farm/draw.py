"""Millet Model Farm: a limewashed, tile-roofed farm barn, millet drilled in straight rows, a seed drill.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/millet_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/millet_model_farm

Identity: the last tier is a managed estate. Mud and thatch give way to a long limewashed barn on
a stone plinth under a red tile roof, with a hoist beam over the loft door and sacks of grain at
the gate. Millet stands in dead-straight drilled rows running back from the viewer, and a
horse-drawn seed drill waits at the bottom right.

Local helpers: the millet helpers of ``millet_farm``, the building helpers of ``millet_farmstead``,
plus ``drilled_row`` (one row of drilled millet in perspective), ``horse`` (draught horse in a collar, from
``carrier_inn``), ``small_wheel``, ``seed_drill`` and ``sack``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 71
REFS = ("farming_village", "kings_manor", "fiber_crops_farm", "free_village")

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


def rim(ic: Icon, m: Image.Image, width: int = 4, color=(40, 24, 12), alpha: float = 0.75) -> None:
    """Soft dark edge just inside a mask (a form's contour without a hard outline)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(2 * width + 1)))
    ic.shade(ring, color, alpha, blur=1)


def drilled_row(ic: Icon, back, front, hw: tuple, h: tuple, t0: float = 0.0, heads=(0.35, 0.62, 0.9)) -> None:
    """One drilled row of millet running from ``back`` to ``front`` (ground points): a narrow band of
    plants whose height grows towards the viewer, lit on its left flank, casting a shadow onto the
    soil strip to its right, with a few seed heads along its top. ``t0`` > 0 lets the row fade in."""
    rnd = ic.random
    b, f = np.array(back, float), np.array(front, float)
    ts = np.linspace(t0, 1, 36)

    def g(t):
        return b + (f - b) * t

    def hw_(t):
        return hw[0] + (hw[1] - hw[0]) * t

    def h_(t):
        fade = min(1.0, (t - t0) / 0.22) if t0 else 1.0
        wob = 1 + 0.08 * math.sin(t * 37 + back[0])
        return (h[0] + (h[1] - h[0]) * t) * (0.35 + 0.65 * fade) * wob

    L = [tuple(g(t) - (hw_(t), 0)) for t in ts]
    R = [tuple(g(t) + (hw_(t), 0)) for t in ts]
    Lt = [(x, y - h_(t)) for (x, y), t in zip(L, ts)]
    Rt = [(x, y - h_(t)) for (x, y), t in zip(R, ts)]
    # cast shadow on the soil strip to the right (light from the upper left)
    ic.shade(ic.poly_mask([(x + 26, y + 4) for x, y in L] + [(x + hw_(t) * 1.3, y + 4) for (x, y), t in zip(R, ts)][::-1]),
             (30, 16, 6), 0.4, blur=8)
    m = union(ic.poly_mask(L + R[::-1]), ic.poly_mask(Lt + Rt[::-1]), ic.poly_mask(L + Lt[::-1]),
              ic.poly_mask(R + Rt[::-1]))
    bb = m.getbbox()
    ic.fill(m, "#7c8a3e", "#26320e", radial=(bb[0], bb[1], (bb[3] - bb[1]) * 1.2), noise=0.3, chroma=0.14)

    def leaves(d):  # upright stalks and arching blades inside the row
        n = int((bb[3] - bb[1]) * 0.9)
        for _ in range(n):
            t = rnd.uniform(t0, 1)
            x, y = g(t)
            x += rnd.uniform(-1, 1) * hw_(t)
            top = y - h_(t) * rnd.uniform(0.2, 1.0)
            if rnd.random() < 0.55:
                col = (166, 170, 96, 120) if rnd.random() < 0.4 else (22, 30, 8, 120)
                d.line([(x, y), (x + rnd.uniform(-6, 6), top)], fill=col, width=rnd.choice((3, 4)))
            else:
                a = rnd.choice((-1, 1))
                L2 = hw_(t) * rnd.uniform(0.6, 1.1)
                d.line([(x, top), (x + a * L2 * 0.5, top - L2 * 0.25), (x + a * L2, top + L2 * 0.2)],
                       fill=(140, 150, 76, 130), width=4)

    ic.overlay(leaves, m)
    # lit left flank, dark right flank, deeper shade low in the row
    k = 16
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, k, 0)), (230, 226, 150), 0.22, blur=4)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, -k, 0)), (12, 16, 4), 0.45, blur=4)
    tint(ic, ic.poly_mask(L + R[::-1]), m, (20, 22, 6), 0.35, 10)
    rim(ic, m, 3, (24, 30, 8), 0.5)

    def tips(d):  # stalk tips and blade ends breaking the top edge
        for (x, y), t in zip(Lt[::2], ts[::2]):
            for _ in range(2):
                xx = x + rnd.uniform(0, 2 * hw_(t))
                d.line([(xx, y + 6), (xx + rnd.uniform(-10, 10), y - rnd.uniform(12, 34) * (0.5 + t))],
                       fill=(92, 104, 44, 230), width=3)

    ic.overlay(tips)
    for t in heads:
        if t < t0:
            continue
        t += rnd.uniform(-0.04, 0.04)
        x, y = g(t)
        side = rnd.choice((-1, 1))
        s = 0.5 + 0.6 * t
        head(ic, (x + rnd.uniform(-0.5, 0.5) * hw_(t), y - h_(t) + 8), -90 + side * 8, side * rnd.uniform(160, 190),
             150 * s, 44 * s, rnd.choice(HEADS), neck=0.2)


def horse(ic: Icon, X: float, G: float, s: float = 1.0, bend: float = 0.18) -> tuple[float, float]:
    """Bay draught horse in profile facing left, head a little lowered, in a padded collar with a
    trace running back along its flank. Lit from the upper left. Returns the collar point."""

    def sm(t: float) -> float:
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def turn(x: float, y: float) -> tuple[float, float]:
        w = sm((130 - x) / 90) * sm((y - 230) / 60)
        a = bend * w
        dx, dy = x - 130, y - 290
        return 130 + dx * math.cos(a) - dy * math.sin(a), 290 + dx * math.sin(a) + dy * math.cos(a)

    def P(pts):
        out = []
        for x, y in pts:
            u, v = turn(x, y)
            out.append((X + u * s, G - v * s))
        return out

    body_c = ("#a8683a", "#3a1c0a")
    for hx, hw in ((46, 42), (122, 38), (262, 40), (314, 40)):
        cx = X + (hx + hw / 2) * s
        tint(ic, ic.mask("ellipse", (cx - 34 * s, G - 8 * s, cx + 34 * s, G + 12 * s)), None, (10, 6, 2), 0.6, 5)
    far_fore = P([(100, 200), (112, 120), (122, 64), (124, 26), (122, 0), (160, 0), (154, 24), (150, 64), (146, 120),
                  (156, 200)])
    far_hind = P([(262, 200), (268, 140), (280, 92), (276, 40), (270, 22), (262, 0), (302, 0), (300, 22), (304, 40),
                  (312, 96), (326, 124), (336, 170), (330, 215)])
    for leg in (far_fore, far_hind):
        lm = ic.poly_mask(leg)
        ic.fill(lm, "#4a2e1c", "#160c06", (G - 200 * s, G), noise=0.14)
        rim(ic, lm, 3, (14, 8, 4), 0.6)
    tail = P([(372, 262), (394, 250), (408, 190), (404, 120), (396, 92), (380, 110), (376, 176), (364, 232)])
    ic.fill(ic.poly_mask(tail), "#3a2418", "#120a06", (G - 262 * s, G - 92 * s), noise=0.2)
    body = P([(44, 215), (52, 185), (90, 168), (180, 158), (260, 166), (300, 184), (330, 190), (370, 215), (384, 248),
              (372, 272), (330, 286), (250, 272), (170, 274), (126, 290), (96, 322), (64, 362), (40, 390), (26, 398),
              (8, 394), (-10, 370), (-30, 330), (-46, 298), (-54, 282), (-46, 268), (-24, 268), (-4, 282), (14, 300),
              (34, 298), (50, 270)])
    near_fore = P([(56, 206), (60, 120), (62, 64), (56, 26), (46, 0), (88, 0), (90, 24), (92, 64), (104, 120),
                   (122, 200)])
    near_hind = P([(290, 200), (298, 140), (318, 94), (320, 40), (318, 22), (314, 0), (354, 0), (350, 22), (348, 40),
                   (352, 96), (362, 124), (374, 170), (366, 220)])
    bm = union(ic.poly_mask(body), ic.poly_mask(near_fore), ic.poly_mask(near_hind))
    xs = [p[0] for p in body]
    ic.fill(bm, body_c[0], body_c[1], radial=(min(xs) + 60 * s, G - 420 * s, 480 * s), noise=0.14)
    lit = ImageChops.subtract(bm, ImageChops.offset(bm, int(12 * s), int(26 * s)))
    tint(ic, lit, bm, (255, 208, 150), 0.42, 7 * s)
    under = ImageChops.subtract(bm, ImageChops.offset(bm, int(-6 * s), int(-30 * s)))
    tint(ic, under, bm, (12, 6, 2), 0.5, 10 * s)
    tint(ic, ic.mask("rectangle", (X, G - 196 * s, X + 400 * s, G)), bm, (10, 4, 0), 0.3, 16)
    tint(ic, ic.mask("ellipse", tuple(P([(276, 282)])[0]) + tuple(P([(356, 206)])[0])), bm, (255, 214, 170), 0.26, 14)
    tint(ic, ic.mask("rectangle", (X, G - 70 * s, X + 400 * s, G)), bm, (20, 12, 8), 0.7, 8)
    rim(ic, bm, 4, (30, 14, 6), 0.7)
    mane = P([(128, 292), (98, 328), (66, 368), (40, 396), (30, 384), (54, 354), (84, 316), (114, 286)])
    ic.fill(ic.poly_mask(mane), "#2e1c12", "#0e0806", noise=0.2)
    ic.poly(P([(30, 398), (38, 428), (50, 400)]), "#9a643a", "#3a2214", edge=3)  # ears
    ex, ey = P([(4, 366)])[0]
    ic.draw.ellipse((ex - 5, ey - 4, ex + 5, ey + 4), fill=(18, 12, 10, 255))
    # padded collar round the base of the neck, hames on it, a trace back along the flank
    collar = P([(60, 356), (84, 380), (136, 300), (150, 226), (126, 214), (112, 288)])
    ic.poly(collar, "#6a4428", "#2a180c", edge=4)
    ic.line(P([(78, 360), (124, 290), (136, 232)]), max(int(8 * s * 2), 5), (170, 150, 120))  # hames
    ic.line(P([(140, 250), (240, 244), (340, 238)]), max(int(10 * s * 2), 6), (54, 34, 18))  # trace
    ic.line(P([(200, 270), (204, 170)]), max(int(10 * s * 2), 6), (54, 34, 18))  # belly band
    ic.line(P([(-40, 300), (0, 300), (60, 340)]), 5, (54, 34, 18))  # bridle
    return P([(140, 246)])[0]


def small_wheel(ic: Icon, cx: float, cy: float, r: float, spokes: int = 8) -> None:
    """Small spoked wooden wheel seen almost side-on, mid-brown with a thin iron tyre."""
    rx, ry = r * 0.84, r
    outer = ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    inner = ic.mask("ellipse", (cx - rx + 14, cy - ry + 14, cx + rx - 14, cy + ry - 14))
    ic.shade(inner, (20, 12, 4), 0.35)  # the ground seen through the spokes, a little shaded
    ic.fill(ImageChops.subtract(outer, inner), "#8a6a48", "#4a3420", radial=(cx - rx, cy - ry, r * 2.2), noise=0.15)
    for k in range(spokes):
        a = 2 * math.pi * k / spokes
        ic.line([(cx, cy), (cx + math.cos(a) * (rx - 10), cy + math.sin(a) * (ry - 10))], 8, (92, 66, 40))
        ic.line([(cx - 1, cy - 1), (cx + math.cos(a) * (rx - 12) - 1, cy + math.sin(a) * (ry - 12) - 1)], 3,
                (170, 132, 88))
    ic.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), "#a07850", "#5a3a20", edge=3)
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(84, 76, 70, 220), width=4))


def seed_drill(ic: Icon, x0: float, x1: float, base: float, hitch) -> None:
    """Horse seed drill seen three-quarter from the front left: a long narrow hopper box, a row of
    thin coulter tubes down to the soil, small wheels at both ends, shafts forward to ``hitch``."""
    rnd = ic.random
    r = 40
    dx, dy = 24, -20  # depth of the box, receding to the upper right
    top, face = base - 214, base - 164
    # far shaft (behind the box and the horse's far side)
    ic.line([(x0 + 20, face + 8), (hitch[0] + 20, hitch[1] - 10)], 10, (60, 42, 24))
    # far wheel, partly hidden by the box
    small_wheel(ic, x1 - 12 + dx, base - r + dy, r)
    # coulter tubes: thin iron-bound wooden tubes to small shoes in the soil
    ic.shade(ic.mask("rectangle", (x0, base - 14, x1 + dx, base + 8)), alpha=0.45, blur=8)
    for i, x in enumerate(np.linspace(x0 + 40, x1 - 30, 6)):
        ic.line([(x, face + 12), (x - 8, base - 12)], 10, (54, 40, 26))
        ic.line([(x - 2, face + 12), (x - 10, base - 12)], 5, (176, 146, 100))
        ic.poly([(x - 16, base - 18), (x + 2, base - 18), (x - 4, base + 2), (x - 18, base - 2)], "#7a7672", "#3a3634",
                edge=2)
    # hopper: lid seen from above, the long front face, an end face
    lid = [(x0, top), (x1, top), (x1 + dx, top + dy), (x0 + dx, top + dy)]
    ic.poly(lid, "#c89a62", "#94704a", edge=3)
    ic.line([(x0 + 8, top + dy / 2), (x1 + dx - 8, top + dy / 2)], 3, (70, 48, 26, 150))
    end = [(x1, top), (x1 + dx, top + dy), (x1 + dx, face + dy), (x1, face)]
    ic.poly(end, "#6e4c2e", "#4a321c", edge=3)
    fm = ic.poly_mask([(x0, top), (x1, top), (x1 - 10, face), (x0 + 10, face)])
    ic.fill(fm, "#8a5a34", "#5a361c", (x0, x1), vertical=False, noise=0.25, chroma=0.12)
    ic.line([(x0 + 4, top + 18 + rnd.uniform(-1, 1)), (x1 - 4, top + 18)], 3, (60, 40, 20, 130))
    for x in (x0 + 14, (x0 + x1) / 2, x1 - 14):
        ic.line([(x, top + 2), (x, face - 2)], 5, (88, 80, 72))
    ic.outline([(x0, top), (x1, top), (x1 - 10, face), (x0 + 10, face)], 3, (50, 32, 16, 170))
    # frame bar under the box carrying the tubes, handles rising at the back right
    ic.line([(x0 - 6, face + 8), (x1 + 8, face + 8)], 9, (84, 58, 34))
    ic.line([(x1 - 6, face + 24), (x1 + 34, top - 36)], 8, (84, 58, 34))
    ic.line([(x1 + 20, face + 24), (x1 + 50, top - 30)], 8, (84, 58, 34))
    # near wheel at the front left end
    small_wheel(ic, x0 - 2, base - r, r)
    # near shaft forward to the collar
    ic.line([(x0 + 10, face + 20), hitch], 12, (60, 42, 24))
    ic.line([(x0 + 10, face + 17), (hitch[0], hitch[1] - 3)], 6, (156, 118, 76))


def sack(ic: Icon, cx: float, base: float, w: float, h: float, color=(164, 128, 84), lean: float = 0) -> None:
    """Tied hessian sack of grain, lit from the upper left, darker than the limewash behind it."""
    body = ic.jitter(cx, base - h * 0.44, w * 0.5, h * 0.46, 14, 0.05)
    body = [(x + lean * (base - y) / h, min(y, base)) for x, y in body]
    dark = tuple(int(v * 0.42) for v in color)
    ic.shade(ic.mask("ellipse", (cx - w * 0.6, base - 10, cx + w * 0.7, base + 10)), alpha=0.5, blur=6)
    ic.fill(ic.poly_mask(body), color, dark, radial=(cx - w * 0.4, base - h * 0.9, w * 1.3), noise=0.28)
    ic.outline(body, 3, (50, 36, 20, 190))
    tx = cx + lean
    ic.poly([(tx - 12, base - h * 0.86), (tx - 18, base - h * 1.04), (tx + 16, base - h * 1.06), (tx + 10, base - h * 0.86)],
            color, dark, edge=3)
    ic.line([(tx - 14, base - h * 0.88), (tx + 12, base - h * 0.88)], 6, (70, 48, 24))


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.72
    ic.grade["mute"] = 0.84

    # ---- the barn: stone plinth, limewashed walls, red tile roof, loft door with hoist beam
    L, R, EAVE, BASE = 400, 990, 430, 700
    ic.tiles([(L - 40, EAVE + 16), (R + 36, EAVE + 16), (R - 90, 250), (L + 100, 250)], "#b0583a", "#6a2c1c",
             course=30, stagger=40)
    ic.rect((L + 96, 236, R - 86, 256), "#8a4a34", "#5a2a1c")  # ridge
    ic.shade(ic.poly_mask([(760, 230), (1030, 230), (1030, 460), (800, 460)]), alpha=0.2, blur=50)
    wall = ic.mask("rectangle", (L, EAVE + 16, R, BASE - 40))
    ic.fill(wall, "#e8dcc2", "#b4a488", (L, R), vertical=False, noise=0.18, chroma=0.06)
    for _ in range(18):  # limewash worn thin in patches, grime rising from the plinth
        x, y = rnd.uniform(L, R), rnd.uniform(EAVE + 40, BASE - 60)
        r = rnd.uniform(16, 40)
        ic.shade(ic.intersect(wall, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6))), (150, 120, 90), 0.12, blur=8)
    ic.shade(ic.intersect(wall, ic.mask("rectangle", (0, BASE - 110, SIZE, SIZE))), (90, 80, 60), 0.3, blur=20)
    ic.shade(ic.mask("rectangle", (L, EAVE + 16, R, EAVE + 70)), alpha=0.5, blur=12)
    ic.stonewall((L, BASE - 50, R, BASE), "#9a8e7c", "#6e6456", course=25)
    # big arched cart door, loft door above it, small dark windows
    ic.door(610, 520, 740, BASE - 50, arched=True, surround="#b8ac94")
    ic.window(470, 540, 520, 596)
    ic.window(900, 540, 950, 596)
    ic.rect((650, 448, 704, 496), "#3a2818", "#1a120a", edge=4)
    ic.beam((620, 446), (732, 446), 14)
    ic.beam((676, 446), (676, 404), 16)
    ic.line([(676, 410), (676, 500)], 4, (60, 50, 40))  # hoist rope
    ic.line([(664, 500), (688, 500)], 6, (60, 50, 40))
    ic.outline([(L, EAVE + 16), (R, EAVE + 16), (R, BASE), (L, BASE)], 4)
    # ---- the yard of packed earth in front of the barn, with wheel ruts
    yard = [(470, 694), (996, 694), (1006, 820), (990, 1000), (540, 1004)]
    ym = ic.poly_mask(yard)
    ic.fill(ym, "#8c7454", "#584430", (694, 1004), noise=0.3, chroma=0.08)
    tint(ic, ic.mask("rectangle", (400, 690, 1000, 740)), ym, (40, 30, 18), 0.45, 14)  # plinth shadow

    def ruts(d):
        for off in (0, 70):
            d.line([(640 + off, 700), (700 + off * 1.3, 820), (760 + off * 1.6, 1000)], fill=(70, 54, 36, 120), width=10)
            d.line([(646 + off, 700), (706 + off * 1.3, 820), (768 + off * 1.6, 1000)], fill=(200, 180, 150, 70), width=3)
        for _ in range(80):
            x, y = rnd.uniform(480, 1000), rnd.uniform(700, 1000)
            r = rnd.uniform(3, 7)
            d.ellipse((x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6),
                      fill=(224, 206, 170, 70) if rnd.random() < 0.5 else (50, 36, 20, 80))

    ic.overlay(ruts, ym)

    # hessian sacks of millet stacked at the gate
    for x, h, b, lean in ((780, 132, BASE + 2, 0), (846, 118, BASE + 6, 6), (812, 96, BASE + 14, -4),
                          (886, 90, BASE + 12, 8)):
        sack(ic, x, b, 78, h, lean=lean)

    # ---- the field: four drilled rows on pale soil, running back towards the barn
    vx, vy = 520, 200
    rows = [60, 212, 364, 516]
    yb, yf = 600, 1000
    k = (yb - vy) / (yf - vy)

    def back(xf):
        return vx + (xf - vx) * k

    fl = [(back(rows[0]) - 40, yb + 40), (back(rows[0]) + 10, yb - 6), (back(rows[-1]) + 60, yb - 8),
          (rows[-1] + 90, yf), (rows[0] - 70, yf)]
    fm = ic.poly_mask(fl)
    ic.fill(fm, "#b48c5e", "#7a5836", (yb, yf), noise=0.3, chroma=0.1)
    tint(ic, ic.poly_mask([(back(rows[0]) - 80, yb - 20), (back(rows[0]) + 40, yb - 20), (rows[0] - 10, yf),
                           (rows[0] - 120, yf)]), fm, (60, 40, 20), 0.35, 30)

    def furrows(d):  # light and dark drill lines in the soil strips between the rows
        for a, b2 in zip(rows[:-1], rows[1:]):
            for f in (0.3, 0.5, 0.7):
                xf = a + (b2 - a) * f
                col = (220, 190, 140, 110) if f == 0.5 else (70, 46, 24, 110)
                d.line([(back(xf), yb), (xf, yf)], fill=col, width=4)
        for _ in range(140):
            x, y = rnd.uniform(0, 700), rnd.uniform(yb, yf)
            r = rnd.uniform(3, 7)
            d.ellipse((x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6),
                      fill=(230, 204, 160, 70) if rnd.random() < 0.5 else (50, 30, 12, 80))

    ic.overlay(furrows, fm)
    for i, xf in enumerate(rows):
        drilled_row(ic, (back(xf), yb), (xf, yf), (12, 36), (80, 172), t0=0.3 if i == 0 else 0.0,
                    heads=(0.4, 0.66, 0.92) if i else (0.62, 0.92))

    # ---- a horse in the shafts of the seed drill, bottom right, heading left away from the barn
    G = 988
    hitch = horse(ic, 560, G, 0.5)
    seed_drill(ic, 770, 928, G, hitch)
