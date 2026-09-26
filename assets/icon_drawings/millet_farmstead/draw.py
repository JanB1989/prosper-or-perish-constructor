"""Millet Farmstead: a raised round granary and a mud-walled house, millet and sealed seed jars.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/millet_farmstead/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/millet_farmstead

Identity: the second tier adds the farm buildings of the dry lands. A round mud granary stands on
stone legs under a conical thatch hat, a notched log leaning on it; behind it a mud-walled house
with a hipped thatch roof. Millet with drooping heads grows at the left, and sealed clay seed jars
and a heap of cut heads stand at the bottom right.

Local helpers: the millet helpers of ``millet_farm`` (``blade``, ``head``, ``millet``, ``stand``,
``soil``, ``thatch_cap``), plus ``mud`` (plastered earth texture), ``cone`` (conical thatch hat),
``granary`` (round raised store), ``jar`` (sealed clay jar) and ``heap_of_heads``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 44
REFS = ("farming_village", "granary", "fiber_crops_farm", "great_enclosure")

HEADS = (("#c98a2a", "#5a300a"), ("#b8742a", "#4a2608"), ("#d29c3c", "#6a4212"), ("#ac6c2c", "#482608"))
BLADE = ("#86984a", "#2a3812")
BLADE_DRY = ("#c8aa62", "#6a5020")


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
           colors=None, dry: float = 0.3, leaves: int = 6, hs: float = 1.0) -> None:
    """One millet plant: stalk, arching strap leaves, a thick seed head hanging to ``side``."""
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
    wid = h * 0.068
    for k, (t, s, up, L, cols) in enumerate(specs):
        if k % 3 == 0:
            blade(ic, tuple(at(t)), (-up if s > 0 else 180 + up), L, wid, rnd.uniform(0.55, 0.9), cols)
    pts = [tuple(at(t)) for t in np.linspace(0, 1, 10)]
    w = max(int(h * 0.022), 5)
    ic.line(pts, w + 4, (40, 40, 18))
    ic.line(pts, w, mix((70, 84, 36), (118, 100, 56), dry))
    ic.line([(p[0] - w * 0.25, p[1]) for p in pts], max(w // 3, 2), (196, 190, 130, 50))
    for k, (t, s, up, L, cols) in enumerate(specs):
        if k % 3:
            blade(ic, tuple(at(t)), (-up if s > 0 else 180 + up), L, wid, rnd.uniform(0.55, 0.9), cols)
    head(ic, tuple(top), -90 + side * rnd.uniform(0, 12), side * rnd.uniform(175, 195), h * hs * rnd.uniform(0.48, 0.54),
         h * hs * rnd.uniform(0.12, 0.135), colors)


def stand(ic: Icon, rows, x0: float, x1: float, dry: float = 0.3, gap: tuple | None = None, hs: float = 1.0) -> None:
    """Rows of millet in perspective: rows = [(base_y, height, spacing), ...] from back to front.

    Each row shades the one behind it. ``gap`` = (x0, x1, row index from) leaves room for props."""
    rnd = ic.random
    for ri, (base, h, step) in enumerate(rows):
        if ri:
            ic.shade(ic.mask("rectangle", (0, base - h * 0.6, SIZE, base + 10)), (14, 18, 4), 0.3, blur=30)
        xs = list(np.arange(x0 + rnd.uniform(0, step * 0.5), x1, step))
        rnd.shuffle(xs)
        for x in xs:
            if gap and ri >= gap[2] and gap[0] < x < gap[1]:
                continue
            millet(ic, x + rnd.uniform(-step * 0.2, step * 0.2), base + rnd.uniform(-6, 6), h * rnd.uniform(0.88, 1.1),
                   lean=rnd.uniform(-h * 0.08, h * 0.08), dry=dry, hs=hs)


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


def heap_of_heads(ic: Icon, cx: float, base: float, w: float, n: int) -> None:
    """Cut millet heads piled on the ground, laid every which way."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.6, base - 20, cx + w * 0.6, base + 16)), alpha=0.45, blur=8)
    for i in range(n):
        t = i / max(n - 1, 1)
        y = base - 10 - 40 * (1 - abs(2 * t - 1)) * rnd.uniform(0.6, 1.0) - 6 * (i % 3)
        x = cx - w * 0.45 + w * 0.9 * rnd.random()
        deg = rnd.choice((rnd.uniform(-30, 20), rnd.uniform(160, 210)))
        head(ic, (x, y), deg, rnd.uniform(-20, 20), rnd.uniform(110, 140), rnd.uniform(34, 40), rnd.choice(HEADS),
             neck=0.0, bend=1.0)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.72
    ic.grade["mute"] = 0.84

    # ---- house behind: mud walls, dark door, hipped thatch roof
    H0, H1, EAVE, BASE = 500, 972, 520, 832
    wall = ic.mask("rectangle", (H0, EAVE, H1, BASE))
    mud(ic, wall, MUD_DARK, (H0, H1))
    ic.rect((760, 660, 850, BASE), "#2e1c12", "#140c08", edge=4)
    ic.shade(ic.mask("rectangle", (760, 660, 850, 690)), (0, 0, 0), 0.4, blur=6)
    ic.rect((880, 620, 930, 680), "#2a1a10", "#120a06", edge=4)
    ic.line([(750, 656), (860, 656)], 14, (96, 68, 42))  # lintel
    ic.shade(ic.mask("rectangle", (H0, EAVE, H1, EAVE + 60)), alpha=0.5, blur=14)
    ic.outline([(H0, EAVE), (H1, EAVE), (H1, BASE), (H0, BASE)], 4)
    thatch_cap(ic, [(H0 - 40, EAVE + 26), (620, 360), (870, 356), (H1 + 40, EAVE + 30), (H1 + 30, EAVE + 50),
                    (H0 - 30, EAVE + 46)], strokes=1400)
    ic.shade(ic.poly_mask([(800, 340), (1024, 340), (1024, 600), (820, 600)]), alpha=0.18, blur=40)

    # ---- ground strip
    top = [(30, 900)] + [(x, 850 + rnd.uniform(-10, 10)) for x in np.linspace(90, 940, 10)] + [(996, 880)]
    soil(ic, top + [(1010, 996), (520, 1008), (60, 1000), (20, 950)], clods=50)
    ic.shade(ic.mask("rectangle", (H0, BASE - 10, H1, BASE + 30)), alpha=0.4, blur=12)

    # ---- a patch of millet behind the granary, at the left
    stand(ic, [(880, 330, 62)], 30, 300, dry=0.5, hs=1.3)

    # ---- the raised granary
    GX, GR = 410, 150
    granary(ic, GX, GR, 460, 720, 900)
    ic.shade(ic.mask("ellipse", (GX - 200, 880, GX + 220, 930)), alpha=0.45, blur=14)
    cone(ic, GX + 4, 180, 440, GR * 1.55, sag=46)
    ic.shade(ic.mask("rectangle", (GX - GR * 1.2, 470, GX + GR * 1.2, 540)), (20, 10, 4), 0.45, blur=16)
    # notched climbing log leaning on the store
    ic.line([(GX + 150, 900), (GX + 60, 560)], 30, (48, 32, 18))
    ic.line([(GX + 146, 900), (GX + 56, 560)], 22, (140, 104, 66))
    for t in np.linspace(0.12, 0.9, 6):
        x, y = GX + 150 - 90 * t, 900 - 340 * t
        ic.line([(x - 14, y), (x + 12, y + 6)], 6, (60, 40, 20))

    # ---- millet at the left, in front of the granary legs
    for x, side, h in ((70, 1, 470), (196, -1, 430), (300, 1, 380)):
        millet(ic, x + rnd.uniform(-8, 8), 986, h, side=side, lean=rnd.uniform(-24, 24), dry=0.45, hs=1.3, leaves=5)

    # ---- sealed seed jars and cut heads at the bottom right
    ic.shade(ic.mask("ellipse", (600, 950, 1016, 1008)), alpha=0.5, blur=10)
    ic.shade(ic.mask("ellipse", (520, 960, 760, 1004)), alpha=0.45, blur=8)
    for x, y, deg in ((690, 986, 188), (720, 962, 184), (660, 952, 176), (700, 936, 180)):
        head(ic, (x, y), deg, rnd.uniform(-10, 10), 150, 42, rnd.choice(HEADS), neck=0.0, bend=1.0)
    jar(ic, 900, 996, 150, 170)
    jar(ic, 790, 1000, 128, 144, ("#c08058", "#633620"))
