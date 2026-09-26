"""Coal Drift (coal_mine): a timbered drift mouth driven along a black seam into a turfed hillside.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/coal_mine/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/coal_mine

Identity: a low, broad hillside that rises to the upper right, cut open at the front: warm sandstone
beds under a short broken turf lip, one continuous black coal seam running across the face, and the
drift mouth driven into the seam under a small shingled hood on two timber posts. A plank-and-rail
way leads out to a wooden tub of coal on the left, a black coal heap with a shovel stands bottom
right. Tier 0 of the coal chain: no headframe, no wheel (those come with the Colliery). Differs from
the iron pit by the green hill, the level strata and seam, and black coal.
Local helpers shared across the coal family: ``union``, ``tint``, ``paste_clipped``, ``shingles``,
``timber``, ``planks`` (from victualling_yard), ``coal_lump``, ``coal_heap``, ``tub``, ``rails``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("schwaz_mine", "clay_pit", "stone_quarry", "charcoal_maker")

COAL_BODY = ("#2e2e34", "#0c0c0e")
IRON = (44, 42, 42)
GROUND = 905


# ---------------------------------------------------------------- helpers (coal family finish)
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


def shingles(ic: Icon, pts, c1, c2, course: float = 24, stagger: float = 30, edge: int = 6,
             var: float = 1.0) -> Image.Image:
    """Roof plane of short staggered shingles: every tile its own tone and ragged lower edge, a dark
    gap beside it and a soft shadow under it, and a drip edge of tile ends along the eaves."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys, xs = [p[1] for p in pts], [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.18, chroma=0.06)
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys) - course * 0.4, 0
    while y < max(ys) + course:
        x = min(xs) - stagger * (0.5 + 0.5 * (k % 2)) - rnd(0, 8)
        while x < max(xs) + stagger:
            w = stagger * rnd(0.7, 1.2)
            b0, b1 = y + course + rnd(-3, 4), y + course + rnd(-3, 4)
            q = [(x + 2, y), (x + w - 2, y), (x + w - 2, b1), (x + 2, b0)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(24, 12, 6, int(-t * 80 * var)) if t < 0 else (255, 238, 212, int(t * 60 * var)))
            td.line([(x + 3, b0 - 3), (x + w - 3, b1 - 3)], fill=(255, 236, 206, 70), width=3)  # lit butt
            td.line([(x + w - 1, y + 2), (x + w - 1, max(b0, b1))], fill=(34, 18, 10, 150), width=3)  # gap
            sd.line([(x + 2, b0 + 3), (x + w - 2, b1 + 3)], fill=255, width=6)
            x += w
        y += course
        k += 1
    paste_clipped(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.45, 2)
    # drip edge: the lowest course sticks out as a row of tile ends with a dark shadow line under it
    bl, br = max(pts, key=lambda p: (p[1], -p[0])), max(pts, key=lambda p: (p[1], p[0]))
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    drip = tuple((a + b) // 2 for a, b in zip(ImageColor.getrgb(c1), ImageColor.getrgb(c2)))
    x = min(bl[0], br[0]) - 4
    while x < max(bl[0], br[0]) + 4:
        w = stagger * rnd(0.6, 1.0)
        d.polygon([(x + 1, bl[1] - 6), (x + w - 1, bl[1] - 6), (x + w - 2, bl[1] + rnd(4, 10)), (x + 2, bl[1] + rnd(4, 10))],
                  fill=drip + (255,))
        d.line([(x + 3, bl[1] - 4), (x + w - 3, bl[1] - 4)], fill=(230, 196, 150, 150), width=3)
        d.line([(x + w - 1, bl[1] - 5), (x + w - 1, bl[1] + 6)], fill=(30, 16, 8, 200), width=3)
        x += w
    ic.image.alpha_composite(lay)
    if edge:
        ic.outline(pts, edge)
    ic.line([(bl[0] - 2, bl[1] + 10), (br[0] + 2, br[1] + 10)], 4, (30, 18, 10, 190))
    return m


def timber(ic: Icon, p0, p1, width: float, c1="#9a6638", c2="#50301a") -> None:
    """Squared beam: lit upper half, darker lower half, a grain highlight, thin dark rim."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def planks(ic: Icon, pts, c1="#946236", c2="#50301a", board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, grain strokes, soft joints; returns the mask."""
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


def coal_lump(ic: Icon, cx: float, cy: float, r: float, tone: float = 1.0, glint: bool = False) -> None:
    """One angular lump of coal: few sharp facets fanned from an off-centre apex, the facets facing
    the upper-left light cool grey, the others near black; a glint only when asked."""
    R = ic.random
    n = R.randint(4, 6)
    rot = R.uniform(0, 2 * math.pi)
    flat = R.uniform(0.6, 0.85)
    angs = sorted(rot + 2 * math.pi * (i + R.uniform(-0.25, 0.25)) / n for i in range(n))
    pts = [(cx + math.cos(a) * r * R.uniform(0.82, 1.18), cy + math.sin(a) * r * flat * R.uniform(0.82, 1.18))
           for a in angs]
    k = lambda c: tuple(min(255, int(v * tone)) for v in c)  # noqa: E731
    m = ic.poly_mask(pts)
    ic.fill(m, k((66, 66, 76)), k((12, 12, 16)), radial=(cx - r * 0.8, cy - r * 0.8, r * 2.6), noise=0.22, chroma=0.04)
    ax, ay = cx - r * R.uniform(0.0, 0.3), cy - r * flat * R.uniform(0.1, 0.4)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        mx, my = (x0 + x1) / 2 - ax, (y0 + y1) / 2 - ay
        f = (-mx * 0.6 - my * 0.8) / (math.hypot(mx, my) or 1)
        if f > 0.25:
            fill = (150, 158, 178, int((30 + 70 * f) * R.uniform(0.6, 1.0) * tone))
        elif f < -0.2:
            fill = (0, 0, 0, int(70 + 100 * -f))
        else:
            fill = (110, 114, 128, int(R.uniform(0, 45)))
        d.polygon([(ax, ay), (x0, y0), (x1, y1)], fill=fill)
    for p in R.sample(pts, 2):  # crisp ridges between facets
        d.line([(ax, ay), p], fill=(150, 156, 172, 45), width=2)
    paste_clipped(ic, lay, m)
    if glint:
        e = min(range(n), key=lambda i: pts[i][0] + pts[i][1])
        p0, p1 = pts[e], pts[(e + 1) % n]
        ic.line([p0, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)], 3, (228, 236, 248, 200))
    ic.outline(pts, 3, (6, 6, 8, 220))


def lump_size(ic: Icon, big: float = 0.14) -> float:
    """Size factor: a few large slabs, some mid lumps, many small ones."""
    u = ic.random.random()
    if u < big:
        return ic.random.uniform(1.1, 1.4)
    if u < big + 0.34:
        return ic.random.uniform(0.7, 1.0)
    return ic.random.uniform(0.32, 0.55)


def coal_heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float, rows: int) -> Image.Image:
    """Mound of coal: a black gritty body, then lumps of very different sizes laid back to front
    (large slabs mostly low, where they roll); returns the body mask."""
    R = ic.random
    cx = (x0 + x1) / 2
    outline = [(x0, base), (x0 + (cx - x0) * 0.4, base - (base - top) * 0.6), (cx - r * 0.8, top + r * 0.3),
               (cx + r * 0.6, top + r * 0.2), (x1 - (x1 - cx) * 0.35, base - (base - top) * 0.55), (x1, base)]
    ic.poly(outline, COAL_BODY[0], COAL_BODY[1], noise=0.3)
    body = ic.poly_mask(outline)
    lumps = []
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.45 + (base - top - r * 0.8) * t
        half = (x1 - x0) / 2 * (0.2 + 0.74 * t)
        x = cx - half + R.uniform(0, r * 0.3)
        while x < cx + half:
            rr = r * lump_size(ic, 0.05 + 0.18 * t)
            lumps.append((x + rr * 0.5, y + R.uniform(-r * 0.3, r * 0.3), rr))
            x += rr * R.uniform(0.75, 1.05)
    lumps.sort(key=lambda p: p[1] + p[2] * 0.5)
    for x, y, rr in lumps:
        coal_lump(ic, x, y, rr, R.uniform(0.8, 1.15), glint=R.random() < 0.12)
    tint(ic, ic.mask("rectangle", (cx, top, x1 + 20, base + 10)), body, (0, 0, 0), 0.25, 30)  # shadow side
    return body


def tub(ic: Icon, x0: float, x1: float, top: float, bottom: float, load: bool = True) -> None:
    """Wooden coal tub on small iron wheels, heaped with mixed lumps, lit from the upper left."""
    w = x1 - x0
    if load:
        R = ic.random
        lumps = [(0.5, -0.1, 0.2), (0.22, -0.04, 0.13), (0.8, -0.03, 0.12)]
        for _ in range(9):
            lumps.append((R.uniform(0.05, 0.95), R.uniform(-0.12, 0.02), R.uniform(0.05, 0.09)))
        for fx, fy, fr in sorted(lumps, key=lambda p: p[1]):
            coal_lump(ic, x0 + w * fx, top + w * fy, w * fr, R.uniform(0.85, 1.12), glint=R.random() < 0.15)
    body = [(x0 - 8, top), (x1 + 8, top), (x1 - 6, bottom), (x0 + 6, bottom)]
    bm = planks(ic, body, "#9a6a3e", "#4a2c16", board=w / 5)
    ic.overlay(lambda d: d.line([(x0 - 4, (top + bottom) / 2), (x1 + 4, (top + bottom) / 2)], fill=(40, 24, 12, 90),
                                width=3), bm)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top, x1 + 20, bottom)), bm, (0, 0, 0), 0.3, 16)
    for x in (x0 - 2, x1 + 2):  # iron corner straps
        ic.line([(x, top + 2), (x + (4 if x < x1 else -4), bottom - 2)], 9, IRON)
    ic.line([(x0 - 8, top + 4), (x1 + 8, top + 4)], 9, (58, 54, 52))
    ic.line([(x0 - 6, top + 1), (x1 + 6, top + 1)], 2, (180, 170, 160, 120))
    ic.outline(body, 4, (40, 26, 16, 170))
    wr = (bottom - top) * 0.3
    for wx in (x0 + w * 0.2, x1 - w * 0.2):
        ic.ellipse((wx - wr, bottom - wr * 0.4, wx + wr, bottom + wr * 1.6), "#5a5654", "#242222", edge=4)
        ic.draw.ellipse((wx - 6, bottom + wr * 0.6 - 6, wx + 6, bottom + wr * 0.6 + 6), fill=(30, 28, 26, 255))


def rails(ic: Icon, x0: float, x1: float, y: float, gauge: float = 18) -> None:
    """Plank sleepers and a pair of timber rails seen from the raised camera."""
    x = x0
    while x < x1:
        ic.rect((x, y - 6, x + 16, y + gauge + 10), "#7a5232", "#40291a", edge=3)
        x += ic.random.uniform(40, 52)
    for yy in (y, y + gauge):
        ic.line([(x0 - 6, yy), (x1 + 6, yy)], 9, (48, 34, 22))
        ic.line([(x0 - 6, yy - 2), (x1 + 6, yy - 2)], 3, (170, 140, 104, 160))


# ---------------------------------------------------------------- parts
def jag(ic: Icon, knots, dx: float = 4, dy: float = 7) -> list:
    """Densify a polyline with small random wobble (keeps the first and last two knots exact)."""
    pts = [knots[0]]
    for (xa, ya), (xb, yb) in zip(knots[1:-2], knots[2:-1]):
        for t in (0.0, 0.5):
            pts.append((xa + (xb - xa) * t + ic.random.uniform(-dx, dx), ya + (yb - ya) * t + ic.random.uniform(-dy, dy)))
    return pts + list(knots[-2:])


def wavy(y: float, amp: float, phase: float, x0: float = 0, x1: float = 1024, step: float = 32) -> list:
    return [(x, y + amp * math.sin(x / 150 + phase) + amp * 0.5 * math.sin(x / 47 + phase * 2.3))
            for x in np.arange(x0, x1 + step, step)]


# hillside skyline: low on the left behind the tub, rising to a broad crown upper right behind the heap
SKY = [(8, GROUND), (20, 846), (48, 772), (96, 700), (160, 636), (250, 570), (350, 512), (450, 464), (550, 430),
       (650, 394), (740, 352), (820, 322), (880, 306), (930, 310), (972, 340), (1000, 400), (1014, 490), (1018, 600),
       (1018, GROUND)]
# the cut face below a short turf lip, where the sandstone beds and the seam are exposed
FACE = [(150, GROUND), (158, 760), (186, 680), (250, 626), (350, 574), (450, 528), (550, 486), (650, 448),
        (740, 414), (810, 392), (860, 392), (890, 440), (904, 560), (910, GROUND)]
SEAM = (612, 690)  # top and bottom of the coal seam


def grass(ic: Icon, hm: Image.Image, face: Image.Image) -> None:
    """Turf with tonal variation: lit crest, darker lower-left flank and shaded right flank, blotches,
    tufts and a few exposed stones."""
    R = ic.random
    ic.fill(hm, "#a4b058", "#4c5c24", radial=(640, 330, 760), noise=0.34, chroma=0.14)
    turf = ImageChops.subtract(hm, face.filter(ImageFilter.MaxFilter(9)))
    # blotches of lusher and drier grass
    lay = Image.new("L", (ic.size, ic.size), 0)
    dry = Image.new("L", (ic.size, ic.size), 0)
    for _ in range(26):
        x, y = R.uniform(0, 1024), R.uniform(360, GROUND)
        rx, ry = R.uniform(30, 80), R.uniform(12, 28)
        ImageDraw.Draw(lay if R.random() < 0.6 else dry).ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
    tint(ic, lay, turf, (30, 44, 14), 0.3, 10)
    tint(ic, dry, turf, (196, 178, 106), 0.22, 10)
    # darker lower-left flank, shaded right flank, lit crest
    tint(ic, ic.poly_mask([(0, 680), (190, 740), (210, GROUND), (0, GROUND)]), turf, (16, 22, 8), 0.5, 40)
    tint(ic, ic.mask("rectangle", (930, 340, 1080, GROUND)), turf, (8, 12, 4), 0.38, 40)
    crest = ImageChops.subtract(hm, ImageChops.offset(hm, 10, 34))
    tint(ic, crest, turf, (232, 236, 170), 0.3, 8)
    # grass strokes
    strokes = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(strokes)
    for _ in range(200):
        x, y = R.uniform(0, 1024), R.uniform(370, GROUND)
        d.line([(x, y), (x + R.uniform(-5, 5), y - R.uniform(8, 18))],
               fill=(206, 214, 136, int(R.uniform(40, 100))) if R.random() < 0.55 else (38, 48, 18, 90), width=3)
    # tufts: small fans of blades with a dark root
    for _ in range(22):
        x, y = R.uniform(20, 1010), R.uniform(380, GROUND - 10)
        d.ellipse((x - 16, y - 4, x + 16, y + 7), fill=(24, 32, 10, 130))
        for j in range(R.randint(4, 6)):
            a = math.radians(-90 + R.uniform(-45, 45))
            L = R.uniform(22, 38)
            lit = j % 2 == 0
            d.line([(x + R.uniform(-6, 6), y), (x + math.cos(a) * L, y + math.sin(a) * L)],
                   fill=(220, 226, 146, 200) if lit else (40, 52, 18, 190), width=5)
    paste_clipped(ic, strokes, turf)
    # a few exposed stones, sitting in the turf
    for x, y, r in ((96, 812, 18), (262, 628, 14), (716, 440, 16), (962, 470, 20), (560, 492, 11), (40, 872, 12)):
        pts = ic.jitter(x, y, r, r * 0.6, 7, 0.2)
        tint(ic, ic.mask("ellipse", (x - r * 1.1, y, x + r * 1.5, y + r * 0.9)), turf, (10, 12, 4), 0.35, 4)
        m = ic.poly_mask(pts)
        ic.fill(m, "#b4ac98", "#5e584e", radial=(x - r * 0.7, y - r * 0.6, r * 2.4), noise=0.2)
        ic.outline(pts, 3, (50, 44, 36, 200))


def cut_face(ic: Icon, face: Image.Image, face_pts) -> None:
    """Warm sandstone beds of uneven thickness, broken bedding lines, joints, and one continuous seam."""
    R = ic.random
    with ic.clipped(face):
        # beds, top to bottom: (top y, colour lit, colour dark)
        beds = ((360, "#e0b870", "#b88a4c"), (470, "#d49c52", "#a8723a"), (548, "#c89050", "#9a6834"),
                (594, "#7a6858", "#4e4238"), (690, "#6e5a4a", "#463a30"), (708, "#cc8c40", "#94602c"),
                (792, "#e2b872", "#b88c50"), (848, "#b67c3c", "#7a5028"))
        for i, (y, c1, c2) in enumerate(beds):
            y1 = beds[i + 1][0] if i + 1 < len(beds) else 1024
            top = wavy(y, 4, i * 1.7)
            bot = wavy(y1, 4, (i + 1) * 1.7)
            m = ic.poly_mask(top + bot[::-1])
            ic.fill(m, c1, c2, (y, y1), noise=0.3, chroma=0.12)
            # lit ledge on the top of each bed
            tint(ic, ic.poly_mask(top + [(p[0], p[1] + 10) for p in top[::-1]]), m, (255, 240, 205), 0.28, 3)
        # broken bedding lines of uneven thickness
        for y, w in ((470, 6), (548, 7), (594, 4), (708, 4), (756, 3), (792, 8), (848, 5)):
            pts = wavy(y, 4, y * 0.01)
            j = 0
            while j < len(pts) - 1:
                n = R.randint(2, 6)
                seg = pts[j:j + n + 1]
                if len(seg) > 1 and R.random() < 0.8:
                    ic.line(seg, int(w * R.uniform(0.7, 1.3)), (74, 42, 20, 200))
                j += n + R.randint(0, 1)
        # vertical joints, a few per bed, and spalled blocks
        for _ in range(26):
            x, y = R.uniform(150, 900), R.uniform(400, 890)
            if SEAM[0] - 10 < y < SEAM[1] + 10:
                continue
            L = R.uniform(18, 40)
            ic.line([(x, y), (x + R.uniform(-4, 4), y + L)], 3, (70, 46, 26, 130))
            ic.line([(x - 4, y), (x - 4 + R.uniform(-3, 3), y + L)], 2, (255, 236, 196, 70))
        # the coal seam, one continuous band across the whole face
        top, bot = wavy(SEAM[0], 5, 0.4), wavy(SEAM[1], 5, 2.1)
        sm = ic.poly_mask(top + bot[::-1])
        ic.fill(sm, "#3c3c44", "#101014", SEAM, noise=0.4)
        lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for _ in range(26):
            x, y = R.uniform(0, 1024), R.uniform(SEAM[0] + 8, SEAM[1] - 10)
            L = R.uniform(10, 24)
            d.line([(x, y), (x + L, y - L * 0.25)], fill=(196, 206, 226, int(R.uniform(40, 110))), width=3)
        for yy in (SEAM[0] + 26, SEAM[0] + 50):  # cleat lines in the coal
            d.line(wavy(yy, 3, yy), fill=(90, 92, 104, 60), width=2)
        paste_clipped(ic, lay, sm)
        ic.line(top, 4, (255, 236, 200, 90))
        tint(ic, ImageChops.subtract(sm.filter(ImageFilter.MaxFilter(9)), sm), None, (20, 16, 14), 0.45)
        # turf lip: shadow on the rock, a short broken lip of soil with roots
        lip = ImageChops.subtract(face, ImageChops.offset(face, 0, 34))
        tint(ic, lip, None, (20, 12, 6), 0.55, 10)
        tint(ic, ic.mask("rectangle", (660, 420, 920, GROUND)), None, (0, 0, 0), 0.24, 50)
        tint(ic, ic.mask("rectangle", (0, 840, 1024, 1024)), None, (0, 0, 0), 0.22, 30)
        tint(ic, ic.mask("rectangle", (130, 600, 220, GROUND)), None, (0, 0, 0), 0.3, 24)
    ic.outline(face_pts[1:-1], 4, (50, 36, 24, 170))
    # the lip itself: a thin band of dark soil hanging a little over the face, broken into short runs
    top = face_pts[1:-1]
    j = 0
    while j < len(top) - 1:
        n = R.randint(2, 3)
        seg = top[j:j + n + 1]
        if len(seg) > 1:
            lip = seg + [(x + R.uniform(-3, 3), y + R.uniform(8, 16)) for x, y in seg[::-1]]
            ic.poly(lip, "#6a5030", "#3c2a18", edge=0, noise=0.3)
            ic.line(seg, 5, (150, 158, 84))
            for x, y in seg[:-1]:
                if R.random() < 0.6:
                    ic.line([(x, y + 10), (x + R.uniform(-5, 5), y + R.uniform(22, 34))], 3, (72, 52, 34, 170))
        j += n + 1


def hill(ic: Icon) -> Image.Image:
    pts = jag(ic, SKY, 5, 6)
    hm = ic.poly_mask(pts)
    face_pts = jag(ic, FACE, 5, 6)
    face = ic.intersect(ic.poly_mask(face_pts), hm)
    grass(ic, hm, face)
    ic.fill(face, "#c8a068", "#7a5a38", (440, GROUND), noise=0.3)
    cut_face(ic, face, face_pts)
    rim = ImageChops.subtract(hm, hm.filter(ImageFilter.MinFilter(25)))
    ic.shade(rim, alpha=0.2, blur=8)
    ic.outline(pts, 6)
    return hm


def drift_mouth(ic: Icon) -> None:
    """Timbered drift mouth driven into the seam, under a shingled hood that sits on the seam."""
    mt = 626
    mouth = [(384, GROUND), (390, mt), (556, mt), (564, GROUND)]
    ic.poly(mouth, "#241e1a", "#080605", edge=0, noise=0.1)
    for k, (inset, top) in enumerate(((32, 660), (56, 700), (76, 730))):
        col = tuple(int(c * (0.55 - 0.13 * k)) for c in (112, 76, 48))
        w = 16 - 4 * k
        ic.beam((384 + inset, GROUND), (390 + inset, top), w, col)
        ic.beam((562 - inset, GROUND), (556 - inset, top), w, col)
        ic.beam((384 + inset - 8, top), (562 - inset + 8, top), w, col)
    ic.line([(436, GROUND), (462, 740)], 5, (80, 70, 60, 170))
    ic.line([(510, GROUND), (484, 740)], 5, (80, 70, 60, 170))
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.3, blur=18)
    # front set: splayed posts, heavy cap lying in the seam
    timber(ic, (368, GROUND + 4), (382, 606), 40, "#b07446", "#583620")
    timber(ic, (580, GROUND + 4), (566, 606), 40, "#b07446", "#583620")
    tint(ic, ic.mask("rectangle", (388, 620, 558, 670)), None, (0, 0, 0), 0.5, 10)
    timber(ic, (338, 610), (608, 610), 40, "#b8783e", "#5c381c")
    # shingled hood leaning back into the hill, its drip edge over the cap
    tint(ic, ic.poly_mask([(320, 588), (628, 588), (628, 640), (320, 640)]), None, (0, 0, 0), 0.35, 12)
    hood = [(318, 590), (630, 590), (604, 516), (346, 516)]
    shingles(ic, hood, "#a8784a", "#5a3a1c", course=20, stagger=26, edge=6)
    for x in (360, 588):  # brackets
        ic.line([(x, 590), (x + (14 if x < 400 else -14), 604)], 10, (70, 44, 24))


def apron(ic: Icon) -> None:
    """Trodden, coal-dusted ground before the drift."""
    pts = [(14, 962), (40, GROUND - 8), (860, GROUND - 8), (1010, 962)]
    ic.poly(pts, "#7a6a56", "#4a3e32", noise=0.32)
    tint(ic, ic.poly_mask([(320, GROUND), (720, GROUND), (780, 960), (280, 960)]), None, (18, 16, 16), 0.4, 18)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.64
    hill(ic)
    apron(ic)
    drift_mouth(ic)
    rails(ic, 50, 610, 922)
    tub(ic, 90, 340, 772, 894)
    # coal heap and shovel, bottom right
    ic.line([(880, 700), (944, 552)], 18, (28, 18, 12))
    ic.line([(880, 700), (944, 552)], 10, (150, 110, 70))
    coal_heap(ic, 610, 1014, 978, 630, 50, 8)
    blade = [(856, 690), (902, 704), (890, 760), (860, 764), (846, 740)]
    ic.poly(blade, "#7a7672", "#3a3634", edge=5)
