"""Macadam Works (macadam_works): tier 2 of the road chain, a road-works yard for broken-stone roads.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/macadam_works/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/macadam_works

Identity: big conical heaps of broken grey stone with breakers' hammers in them, a heavy
cast-iron road roller in its timber frame with shafts, and a crowned, rolled macadam road with a
side drain. Behind stand a slate-roofed stone works house and an open breaking shed. Grows from the
Paviors' Yard (sett paving, rammers) and precedes the Permanent Way Depot (rails, wagon shed).
Helpers: shared road-family block (``stones``, ``thatch``, ``timber``, ``planks``, ``weeds``,
``mound``, ``pole``), ``shingles`` (victualling_yard), kit ``heap``; new ``roller`` and the
crowned road.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 17
REFS = ("sand_pit", "stone_quarry", "roads", "construction_center")

RT, RB, RF = 796, 900, 940  # road: back edge, front edge, foot of the verge face
IRON = (44, 42, 40)
STONE_LUMP = ("#b0a48c", "#4e4638")
STONE_BODY = ("#7a6e5e", "#3a3228")

# ---------------------------------------------------------------- helpers (road-family finish)
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


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
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
    paste_clipped(ic, lay, m)


def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands down the slope, layered courses with a dark underside,
    weathered blotches. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    shadow = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    paste_clipped(ic, lay, m)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(10):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> Image.Image:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it. Returns the mask."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def planks(ic: Icon, pts, c1="#86603e", c2="#4e3522", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = False, tall: float = 1.0) -> None:
    """Tuft of grass and weeds."""
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(int(w / 4)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 36) * tall
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(92, 132), R.randint(108, 138), R.randint(48, 66), 235)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


def mound(ic: Icon, x0: float, x1: float, base: float, top: float, body=("#a89a84", "#5a5044"),
          pebble: float = 9, density: float = 1.0, peb_col=((236, 226, 206), (40, 34, 28))) -> Image.Image:
    """Heap of loose material (gravel, sand, broken stone, ballast): lumpy crest, radial light from
    the upper left, shadowed right flank, a scatter of lit/dark pebbles. Returns the mask."""
    R = ic.random
    cx = (x0 + x1) / 2 + (x1 - x0) * 0.06
    ts = np.linspace(0, 1, 40)
    pts = []
    for t in ts:
        x = x0 + (x1 - x0) * t
        u = (x - cx) / ((x1 - x0) / 2)
        y = base - (base - top) * max(0.0, 1 - abs(u) ** 1.6) ** 0.9
        pts.append((x, y + R.uniform(-5, 5) * (1 - abs(u))))
    pts += [(x1, base), (x0, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, body[0], body[1], radial=(cx - (x1 - x0) * 0.25, top, (x1 - x0) * 0.85), noise=0.3, chroma=0.08)
    tint(ic, ic.mask("ellipse", (cx, top, x1 + 80, base + 60)), m, (10, 8, 6), 0.3, 30)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    n = int((x1 - x0) * (base - top) / (pebble * pebble * 2.2) * density)
    lit, dk = peb_col
    for _ in range(n):
        x = R.uniform(x0, x1)
        y = R.uniform(top, base)
        r = pebble * R.uniform(0.6, 1.3)
        a = R.randint(70, 150)
        d.ellipse((x - r, y - r * 0.75, x + r, y + r * 0.75), fill=(*dk, a))
        d.ellipse((x - r * 0.8, y - r * 0.85, x + r * 0.5, y + r * 0.2), fill=(*lit, int(a * 0.8)))
    paste_clipped(ic, lay, m)
    ic.outline(pts, 5, (40, 30, 22, 190))
    return m


def pole(ic: Icon, p0, p1, width: float, bands=("#b35a42", "#d8ccb2"), n: int = 7) -> None:
    """Barrier pole painted in bands, shaded as a round spar (lit upper edge, dark underside)."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    for i in range(n):
        a, b = i / n, (i + 1) / n
        q = [(x0 + ux * L * a - nx * h, y0 + uy * L * a - ny * h), (x0 + ux * L * b - nx * h, y0 + uy * L * b - ny * h),
             (x0 + ux * L * b + nx * h, y0 + uy * L * b + ny * h), (x0 + ux * L * a + nx * h, y0 + uy * L * a + ny * h)]
        c = bands[i % 2]
        ic.fill(ic.poly_mask(q), c, tuple(int(v * 0.8) for v in bytes.fromhex(c[1:])), noise=0.2)
    full = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(full)
    under = [(x0, y0), (x1, y1), full[2], full[3]]
    tint(ic, ic.poly_mask(under), m, (20, 10, 6), 0.4)
    ic.line([(x0 - nx * h * 0.5, y0 - ny * h * 0.5), (x1 - nx * h * 0.5, y1 - ny * h * 0.5)], 4, (255, 240, 215, 90))
    ic.outline(full, 4, (40, 26, 16, 190))


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, soft course shadow. Returns the mask."""
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
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    if edge:
        ic.outline(pts, edge)
    return m


def house(ic: Icon) -> None:
    """Gable-fronted stone works house: slate verge, ashlar walls with quoins, arched door, chimney."""
    x0, x1, eave, apex, base = 36, 330, 450, 226, RT + 4
    cx = (x0 + x1) / 2
    stones(ic, (238, 180, 284, 330), "#9a8e7c", "#625a4e", course=24, moss=0.0)
    ic.outline([(238, 180), (284, 180), (284, 330), (238, 330)], 5)
    ic.rect((230, 168, 292, 186), "#7a7066", "#4e4640", edge=5)
    verge = [(x0 - 34, eave + 20), (cx, apex - 40), (x1 + 34, eave + 20), (x1 + 34, eave + 44), (cx, apex - 6),
             (x0 - 34, eave + 44)]
    vm = shingles(ic, [(x0 - 34, eave + 44), (cx, apex - 40), (x1 + 34, eave + 44)], "#6e7076", "#383a40",
                  course=22, stagger=30, edge=0)
    ic.outline([(x0 - 34, eave + 44), (cx, apex - 40), (x1 + 34, eave + 44)], 6)
    wall_pts = [(x0, base), (x0, eave + 26), (cx, apex), (x1, eave + 26), (x1, base)]
    wm = ic.poly_mask(wall_pts)
    stones(ic, (x0, apex, x1, base), "#ccb894", "#8a7658", course=34, clip=wm, moss=0.08)
    tint(ic, ic.mask("rectangle", (cx + 40, apex, x1 + 10, base)), wm, (0, 0, 0), 0.22, 30)
    tint(ic, ic.mask("rectangle", (x0, base - 80, x1, base)), wm, (30, 34, 20), 0.3, 20)
    tint(ic, ic.poly_mask([(x0, eave + 26), (cx, apex), (x1, eave + 26), (x1, eave + 70), (cx, apex + 44),
                           (x0, eave + 70)]), wm, (0, 0, 0), 0.45, 12)  # verge shadow
    ic.outline(wall_pts, 6)
    for qx0, qx1 in ((x0, x0 + 30), (x1 - 30, x1)):  # quoins
        y, k = eave + 40, 0
        while y < base - 30:
            w = (30 if k % 2 else 20)
            bx = (qx0, y, qx0 + w, y + 30) if qx0 == x0 else (qx1 - w, y, qx1, y + 30)
            ic.rect(bx, "#d8ceb8", "#9a907c", edge=0)
            ic.line([(bx[0], bx[3]), (bx[2], bx[3])], 4, (40, 28, 20, 150))
            y += 32
            k += 1
    ic.window(cx - 26, 330, cx + 26, 390)
    ic.door(cx - 44, 620, cx + 44, base - 2, arched=True, surround="#c2b69e")
    ic.window(x0 + 56, 640, x0 + 96, 690)


def breaking_shed(ic: Icon) -> None:
    """Open breaking shed on timber posts: pent slate roof; inside, a stone-breaker's block with a
    pile of broken stone in the light that falls through the opening."""
    x0, x1, eave, back, base = 330, 640, 552, 470, RT + 4
    inner = ic.mask("rectangle", (x0, eave - 20, x1 - 10, base))
    ic.fill(inner, "#54463a", "#2a2018", (eave, base), noise=0.12)
    with ic.clipped(inner):
        planks(ic, [(x0, eave - 20), (x1, eave - 20), (x1, base), (x0, base)], "#6a5642", "#34281c", board=30)
        tint(ic, ic.mask("rectangle", (x0, eave, x1, eave + 90)), None, (0, 0, 0), 0.5, 20)
        tint(ic, ic.mask("ellipse", (x0 - 20, 660, 520, base + 40)), None, (255, 236, 200), 0.16, 30)  # daylight
        # breaker's block and a pile of broken stone beside it
        tint(ic, ic.mask("ellipse", (350, base - 14, 470, base + 12)), None, (0, 0, 0), 0.5, 6)
        ic.rect((360, 734, 424, base), "#a49a88", "#625a4e", edge=4)
        ic.line([(364, 738), (420, 738)], 4, (255, 246, 226, 150))
        tint(ic, ic.mask("rectangle", (398, 740, 424, base)), None, (0, 0, 0), 0.3, 4)
        for _ in range(9):
            sx, sy = ic.random.uniform(424, 470), ic.random.uniform(760, base - 6)
            lump(ic, sx, sy, ic.random.uniform(9, 14))
        lump(ic, 386, 722, 13)
    for i, px in enumerate((x0 + 18, 486, x1 - 14)):
        if i == 0:  # the post in the light
            timber(ic, (px, eave), (px, base), 26, "#b88e64", "#6e4e30")
        else:
            timber(ic, (px, eave), (px, base), 24, "#8a6444", "#4c3420")
    timber(ic, (x0 - 4, eave + 6), (x1 + 10, eave + 6), 26, "#8e6848", "#4e3522")
    roof = [(x0 - 14, eave + 4), (x1 + 44, eave + 4), (x1 + 20, back), (x0, back - 6)]
    rm = shingles(ic, roof, "#7a7c82", "#44464c", course=24, stagger=34, edge=7)
    tint(ic, ic.mask("rectangle", (x0 - 20, back - 10, x0 + 60, eave + 10)), rm, (0, 0, 0), 0.3, 16)  # house shadow
    tint(ic, ic.mask("rectangle", (x0, eave + 20, x1, eave + 70)), None, (0, 0, 0), 0.35, 12)


def lump(ic: Icon, cx: float, cy: float, r: float, base=(150, 142, 126), d: ImageDraw.ImageDraw | None = None) -> None:
    """One broken stone shaped by value only: body tone, a lit top-left facet, a dark underside, a
    faint edge (no kit outline)."""
    R = ic.random
    pts = ic.jitter(cx, cy, r, r * 0.78, R.randint(6, 8), 0.18)
    t = R.uniform(0.78, 1.12)
    warm = R.random()
    k = (1.06, 1.0, 0.92) if warm < 0.25 else (0.95, 0.98, 1.04) if warm < 0.4 else (1, 1, 1)
    col = tuple(int(min(255, v * t * f)) for v, f in zip(base, k))
    own = d is None
    if own:
        lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
    d.polygon(pts, fill=col + (255,))
    under = [(cx - r * 0.95, cy + r * 0.05), (cx + r, cy - r * 0.1), (cx + r * 0.8, cy + r * 0.8), (cx - r * 0.6, cy + r * 0.8)]
    d.polygon(under, fill=tuple(int(v * 0.52) for v in col) + (220,))
    facet = [(cx - r * 0.7, cy - r * 0.05), (cx - r * 0.2, cy - r * 0.62), (cx + r * 0.42, cy - r * 0.48),
             (cx + r * 0.05, cy + r * 0.02)]
    d.polygon(facet, fill=tuple(int(min(255, v * 1.18 + 8)) for v in col) + (220,))
    d.line(pts + [pts[0]], fill=(40, 34, 28, 50), width=3)
    if own:
        clip = ic.poly_mask(pts)
        c = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        c.paste(lay, (0, 0), clip)
        ic.image.alpha_composite(c)


def stone_heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float) -> Image.Image:
    """Conical heap of broken stone: dark cone body, lumps laid back to front and shaped by value,
    lit from the upper left, shadowed right flank, darker contact band at the foot. Returns the mask."""
    cm = cone(ic, x0, x1, base, top)
    cx = (x0 + x1) / 2
    ic.fill(cm, "#8a7e6c", "#463e32", radial=(cx - (x1 - x0) * 0.25, top, (x1 - x0) * 0.9), noise=0.3)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R = ic.random
    rows = int((base - top) / (r * 1.25)) + 1
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.4 + (base - top - r * 0.2) * t
        half = (x1 - x0) / 2 * (0.12 + 0.86 * t)
        n = max(1, int(2 * half / (r * 0.95)))
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + R.uniform(-8, 8)
            u = (x - cx) / ((x1 - x0) / 2)
            shade = 1.08 - 0.34 * max(0.0, u) - 0.12 * t  # light from the upper left
            lump(ic, x, y + R.uniform(-5, 5), r * R.uniform(0.75, 1.1),
                 base=tuple(int(v * shade) for v in (152, 144, 128)), d=d)
    arr = np.asarray(lay).astype(float)
    arr[..., :3] *= (1 + 0.14 * ic.noise)[..., None]
    paste_clipped(ic, Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA"), cm)
    tint(ic, ic.mask("ellipse", (cx, top, x1 + 60, base + 60)), cm, (8, 6, 4), 0.34, 30)
    tint(ic, ic.mask("rectangle", (x0 - 20, base - 34, x1 + 20, base + 30)), cm, (14, 10, 6), 0.5, 10)  # contact band
    return cm


def hammer(ic: Icon, p0, p1, head: float = 26) -> None:
    """Stone-breaker's hammer, head at ``p1``: short haft, a small dark iron block set crosswise
    with a lighter striking face."""
    timber(ic, p0, p1, 11, "#a88058", "#5a3e26")
    x, y = p1
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    nx, ny = -uy, ux
    hw = 9  # half thickness of the head along the haft
    q = [(x - nx * head - ux * hw, y - ny * head - uy * hw), (x + nx * head - ux * hw, y + ny * head - uy * hw),
         (x + nx * head + ux * hw * 1.6, y + ny * head + uy * hw * 1.6),
         (x - nx * head + ux * hw * 1.6, y - ny * head + uy * hw * 1.6)]
    ic.poly(q, (70, 68, 66), (30, 28, 26), edge=0)
    for s in (-1, 1):  # lighter striking faces at both ends of the bar
        e0 = (x + s * nx * head - ux * hw, y + s * ny * head - uy * hw)
        e1 = (x + s * nx * head + ux * hw * 1.6, y + s * ny * head + uy * hw * 1.6)
        ic.line([e0, e1], 6, (176, 172, 164))
    ic.line([q[0], q[1]], 3, (150, 146, 138, 170))
    ic.outline(q, 4, (26, 22, 18, 230))


def cone(ic: Icon, x0: float, x1: float, base: float, top: float) -> Image.Image:
    """Smooth heap silhouette with a slightly lumpy crest."""
    cx = (x0 + x1) / 2
    pts = []
    for t in np.linspace(0, 1, 36):
        x = x0 + (x1 - x0) * t
        u = abs(x - cx) / ((x1 - x0) / 2)
        pts.append((x, base - (base - top) * max(0.0, 1 - u ** 1.25) ** 0.85 + ic.random.uniform(-7, 7)))
    return ic.poly_mask(pts + [(x1 + 6, base + 30), (x0 - 6, base + 30)])


def heaps(ic: Icon) -> None:
    """A big conical heap of broken stone and a clearly smaller, lower one; one hammer stuck in the
    big heap, one lying on the small heap's flank."""
    tint(ic, ic.mask("ellipse", (500, RT - 30, 1020, RT + 34)), None, (0, 0, 0), 0.45, 14)
    stone_heap(ic, 842, 1012, RT + 8, 660, 15)
    stone_heap(ic, 520, 860, RT + 12, 430, 19)
    tint(ic, ic.mask("ellipse", (720, 440, 920, RT + 40)), None, (0, 0, 0), 0.18, 40)
    hammer(ic, (640, 520), (608, 414))
    hammer(ic, (884, 700), (968, 668), 22)  # laid on the small heap's flank


def roller(ic: Icon) -> None:
    """Cast-iron road roller: a big drum (cylindrical light, elliptical end disc) in a timber frame
    with bearing blocks, one pair of shafts lying forward on the road."""
    x0, x1, cy, r = 470, 724, 800, 86
    tint(ic, ic.mask("ellipse", (x0 - 40, cy + r - 26, x1 + 120, cy + r + 24)), None, (0, 0, 0), 0.75, 10)
    timber(ic, (x0 + 10, 744), (236, 868), 16, "#7a5a3c", "#4c3420")  # far shaft
    body = ic.mask("rectangle", (x0, cy - r, x1, cy + r))
    ic.fill(body, "#6e6a64", "#1c1a18", (cy - r, cy + r), noise=0.1, chroma=0.03)
    tint(ic, ic.mask("rectangle", (x0, cy - r, x1, cy - r + 20)), body, (0, 0, 0), 0.25, 8)  # top edge turns away
    tint(ic, ic.mask("rectangle", (x0, cy - r * 0.5, x1, cy - r * 0.2)), body, (240, 236, 226), 0.55, 8)  # specular band
    tint(ic, ic.mask("rectangle", (x0, cy + r * 0.33, x1, cy + r)), body, (0, 0, 0), 0.5, 10)  # dark lower third
    tint(ic, ic.mask("rectangle", (x0, cy + r - 22, x1, cy + r)), body, (130, 110, 80), 0.2, 6)  # reflected road light
    tint(ic, ic.mask("rectangle", (x1 - 50, cy - r, x1, cy + r)), body, (0, 0, 0), 0.22, 16)
    for _ in range(10):  # rust and road dirt
        rx, ry = ic.random.uniform(x0, x1), ic.random.uniform(cy - r, cy + r)
        tint(ic, ic.mask("ellipse", (rx - 24, ry - 9, rx + 24, ry + 9)), body, (130, 76, 40), 0.22, 6)
    ic.outline([(x0, cy - r), (x1, cy - r), (x1, cy + r), (x0, cy + r)], 6)
    # end disc: slightly elliptical, a lit face inside a darker rim
    ex = 40
    cap = ic.mask("ellipse", (x0 - ex, cy - r, x0 + ex, cy + r))
    ic.fill(cap, "#3a3634", "#1e1c1a", (cy - r, cy + r), noise=0.1)
    face = ic.mask("ellipse", (x0 - ex + 10, cy - r + 12, x0 + ex - 10, cy + r - 12))
    ic.fill(face, "#aaa69e", "#4e4a46", radial=(x0 - ex * 0.6, cy - r * 0.6, r * 1.9), noise=0.12)
    ic.overlay(lambda d: d.ellipse((x0 - ex, cy - r, x0 + ex, cy + r), outline=(30, 24, 20, 230), width=6))
    ic.overlay(lambda d: d.ellipse((x0 - 12, cy - 18, x0 + 12, cy + 18), fill=(52, 50, 48, 255)))
    # frame: cheeks down to the axle, heavy top rail with a driver's step
    for fx in (x0 - 2, x1 + 8):
        timber(ic, (fx, cy + 8), (fx, cy - r - 30), 28, "#946c4a", "#4e3522")
        ic.draw.ellipse((fx - 15, cy - 8, fx + 15, cy + 22), fill=(52, 50, 48, 255))
        ic.draw.ellipse((fx - 5, cy + 2, fx + 5, cy + 12), fill=(140, 136, 128, 255))
    timber(ic, (x0 - 22, cy - r - 26), (x1 + 26, cy - r - 26), 28, "#9a7250", "#523823")
    ic.line([(x0 + 60, cy - r - 12), (x0 + 60, cy - r + 4)], 6, IRON)
    ic.line([(x1 - 60, cy - r - 12), (x1 - 60, cy - r + 4)], 6, IRON)
    timber(ic, (x0 - 6, 770), (190, 884), 20, "#9a7450", "#5a3e26")  # near shaft
    ic.line([(292, 830), (294, 866)], 6, IRON)


def road(ic: Icon) -> None:
    """Crowned macadam road: a light, finely speckled rolled surface with a soft crown highlight
    along its centre; a dark stone-lined drain along the near edge with light kerb stones in front,
    and a verge face."""
    DR = RB - 16  # back of the drain
    top = [(46, RT), (978, RT), (1004, DR), (20, DR)]
    m = ic.poly_mask(top)
    ic.fill(m, "#c4baa6", "#948a78", (RT, DR), noise=0.2, chroma=0.05)
    tint(ic, ic.mask("rectangle", (0, RT + 30, 1024, RT + 50)), m, (255, 250, 236), 0.4, 10)  # crown highlight
    tint(ic, ic.mask("rectangle", (0, RT, 1024, RT + 12)), m, (0, 0, 0), 0.26, 6)
    tint(ic, ic.mask("rectangle", (0, DR - 20, 1024, DR)), m, (0, 0, 0), 0.22, 8)  # falls away to the drain
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    R = ic.random
    for _ in range(1600):  # fine grit
        x, y = R.uniform(14, 1010), R.uniform(RT + 2, DR - 2)
        rr = R.uniform(1.5, 3.2)
        d.ellipse((x - rr, y - rr * 0.7, x + rr, y + rr * 0.7), fill=(52, 46, 38, 120) if R.random() < 0.5
                  else (250, 246, 234, 120))
    paste_clipped(ic, lay, m)
    # drain: dark channel, then light kerb stones along the front edge
    ch = ic.poly_mask([(20, DR), (1004, DR), (1008, RB - 2), (16, RB - 2)])
    ic.fill(ch, "#3e4244", "#1e2224", (DR, RB), noise=0.1)
    ic.line([(40, DR + 9), (980, DR + 10)], 3, (150, 164, 168, 150))
    kb = ic.mask("rectangle", (14, RB - 2, 1010, RB + 14))
    ic.fill(kb, "#d6ccb6", "#a89e88", (RB - 2, RB + 14), noise=0.18)
    x = 14
    while x < 1000:
        x += R.uniform(70, 110)
        ic.line([(x, RB - 2), (x + 2, RB + 14)], 3, (60, 52, 42, 180))
    ic.line([(16, RB), (1008, RB)], 3, (255, 250, 236, 150))
    face = [(14, RB + 14), (1010, RB + 14), (1002, RF), (22, RF)]
    fm = ic.poly_mask(face)
    stones(ic, (14, RB + 12, 1010, RF), "#9a9080", "#5e564a", course=26, clip=fm, moss=0.2)
    tint(ic, ic.mask("rectangle", (0, RB + 12, 1024, RB + 22)), fm, (0, 0, 0), 0.3, 4)
    ic.outline(top[:2] + [(1010, RB - 2), (1010, RB + 14), (1002, RF), (22, RF), (14, RB + 14), (14, RB - 2)], 6)
    for x in range(40, 1000, 110):
        weeds(ic, x + R.uniform(-20, 20), RF - 2, R.uniform(24, 40), tall=0.8)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 1.0
    house(ic)
    breaking_shed(ic)
    heaps(ic)
    road(ic)
    tint(ic, ic.mask("rectangle", (30, RT - 6, 640, RT + 20)), None, (0, 0, 0), 0.35, 8)
    roller(ic)
