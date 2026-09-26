"""Road Wardens' Yard (road_wardens_yard): tier 0 of the road chain, a roadside warden's lodge.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/road_wardens_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/road_wardens_yard

Identity: a small thatched rubble lodge beside a rutted earth road, its toll bar swung up on a
post with a stone counterweight, a pale milestone on the near verge and a heap of gravel with a
shovel for filling the ruts. Road family: the road band runs across the front of every tier and its
surface grows with the chain (earth track, setts, crowned macadam, wagonway).
Helpers: ``union``, ``tint``, ``paste_clipped``, ``stones``, ``thatch`` (tavern/cookshop),
``timber``, ``planks``, ``weeds`` (canal_lock_works), new ``mound`` (gravel/sand/ballast heap) and
``pole`` (banded barrier pole).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("roads", "toll_castle", "tambo", "caravan_stop")

RT, RB, RF = 800, 900, 932  # road: back edge, front edge, foot of the verge face
IRON = (44, 42, 40)


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


# ---------------------------------------------------------------- parts
def clump(ic: Icon, x: float, y: float, w: float, tall: float = 1.0) -> None:
    """Big grass clump that survives 1x: dark mass at the root, blades, sunlit lighter tops."""
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse((x - w * 0.5, y - 22 * tall, x + w * 0.5, y + 8), fill=(56, 66, 32, 235))
    blades = []
    for _ in range(int(w / 3.2)):
        bx = x + R.uniform(-w * 0.48, w * 0.48)
        k = 1 - abs(bx - x) / w
        h = R.uniform(34, 66) * tall * k
        tip = (bx + (bx - x) * 0.45 + R.uniform(-12, 12), y - h)
        mid = ((bx + tip[0]) / 2 + R.uniform(-5, 5), (y + tip[1]) / 2)
        blades.append((bx, mid, tip))
        d.line([(bx, y), mid, tip], fill=(R.randint(66, 92), R.randint(84, 104), R.randint(36, 48), 245), width=7,
               joint="curve")
    for bx, mid, tip in blades:  # lighter tops, strongest on the lit (left) side
        lit = 1.0 if bx < x + w * 0.1 else 0.55
        d.line([mid, tip], fill=(R.randint(150, 178), R.randint(160, 180), R.randint(84, 100), int(215 * lit)), width=4,
               joint="curve")
    ic.image.alpha_composite(lay)


def road(ic: Icon) -> Image.Image:
    """Rutted earth road running across the front: uneven edges, lighter crowned earth between two
    soft broken wheel ruts of damp dark soil, a muddy puddle lying in the near rut, loose pebbles
    along the edges and a low earth verge face."""
    R = ic.random
    xs = np.linspace(0, 1, 34)
    back = [(64 + 898 * t, RT + 7 * math.sin(t * 11.3 + 1) + 4 * math.sin(t * 29) + R.uniform(-2, 2)) for t in xs]
    front = [(14 + 996 * t, RB + 5 * math.sin(t * 9.1 + 2) + 3 * math.sin(t * 31) + R.uniform(-2, 2)) for t in xs]
    top = back + front[::-1]
    m = ic.poly_mask(top)
    ic.fill(m, "#a4896a", "#77603f", (RT, RB), noise=0.32, chroma=0.1)

    def rut(y_left: float, y_right: float, width: float, phase: float) -> list:
        pts = [(x, y_left + (y_right - y_left) * (x / 1024) + 5 * math.sin(x / 70 + phase) + 2 * math.sin(x / 23))
               for x in np.linspace(20, 1004, 70)]
        segs, i = [], 0
        while i < len(pts) - 2:  # broken: worn stretches with short gaps
            n = R.randint(8, 16)
            segs.append(pts[i:i + n])
            i += n + R.randint(1, 2)
        return segs

    crown = [(x, RT + 50 + 3 * math.sin(x / 80)) for x in np.linspace(20, 1004, 30)]
    cm = Image.new("L", (ic.size, ic.size), 0)
    ImageDraw.Draw(cm).line(crown, fill=255, width=22)
    tint(ic, cm, m, (238, 218, 180), 0.32, 9)  # lighter crowned earth between the ruts
    for yl, yr, wd, ph in ((RT + 26, RT + 36, 15, 0.7), (RT + 76, RT + 66, 20, 2.1)):
        segs = rut(yl, yr, wd, ph)
        dm, lm = Image.new("L", (ic.size, ic.size), 0), Image.new("L", (ic.size, ic.size), 0)
        dd, ld = ImageDraw.Draw(dm), ImageDraw.Draw(lm)
        for s in segs:
            dd.line(s, fill=255, width=int(wd), joint="curve")
            ld.line([(x, y + wd * 0.55) for x, y in s], fill=255, width=5, joint="curve")
        tint(ic, dm, m, (44, 30, 18), 0.7, 3.5)
        tint(ic, lm, m, (240, 222, 190), 0.3, 2.5)
    # muddy puddle lying in the near rut: dull sky reflection, dark rim
    py = RT + 68
    pm = ic.mask("ellipse", (662, py - 11, 772, py + 12))
    ic.fill(pm, "#6c7a7e", "#3e4a4c", (py - 11, py + 12), noise=0.08, chroma=0.02)
    tint(ic, ic.mask("ellipse", (680, py - 8, 736, py + 1)), pm, (168, 182, 184), 0.35, 4)
    ic.overlay(lambda d: d.ellipse((662, py - 11, 772, py + 12), outline=(38, 28, 20, 210), width=4))
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(90):  # loose pebbles along both edges, grit on the crown
        x = R.uniform(20, 1000)
        y = R.choice([R.uniform(RT + 2, RT + 18), R.uniform(RB - 16, RB - 2), R.uniform(RT + 40, RT + 58)])
        r = R.uniform(4, 8) if y < RT + 20 or y > RB - 18 else R.uniform(2, 4)
        d.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.8), fill=(52, 40, 28, 150))
        d.ellipse((x - r * 0.85, y - r * 0.75, x + r * 0.5, y + r * 0.2), fill=(226, 212, 186, 190))
    paste_clipped(ic, lay, m)
    face = front + [(1002, RF), (22, RF)]
    fm = ic.poly_mask(face)
    ic.fill(fm, "#6e5a40", "#433424", (RB, RF), noise=0.3)
    tint(ic, ic.mask("rectangle", (0, RB - 6, 1024, RB + 16)), fm, (0, 0, 0), 0.3, 5)
    ic.outline(back + [front[-1], (1002, RF), (22, RF), front[0]], 5)
    return m


def verge_grass(ic: Icon) -> None:
    for x, y, w, t in ((268, RB + 10, 86, 1.0), (596, RT + 14, 72, 0.9), (846, RB + 10, 96, 1.05),
                       (990, RT + 20, 58, 0.85)):
        clump(ic, x, y, w, t)


def lodge(ic: Icon) -> None:
    """Warden's lodge: rubble walls, deep thatch, a stone chimney, plank door, one small window."""
    x0, x1, eave, ridge, base = 90, 540, 500, 250, RT + 6
    # chimney at the right gable
    stones(ic, (440, 170, 504, 330), "#a0947e", "#6a6052", course=24, moss=0.0)
    ic.outline([(440, 170), (504, 170), (504, 330), (440, 330)], 5)
    ic.rect((432, 158, 512, 178), "#8a7e6c", "#5a5246", edge=5)
    tint(ic, ic.mask("rectangle", (476, 170, 510, 330)), None, (0, 0, 0), 0.25, 6)
    wall = ic.mask("rectangle", (x0, eave - 10, x1, base))
    stones(ic, (x0, eave - 10, x1, base), "#b4a68e", "#716656", course=40, clip=wall, moss=0.1)
    ic.outline([(x0, eave - 10), (x1, eave - 10), (x1, base), (x0, base)], 6)
    tint(ic, ic.mask("rectangle", (x1 - 130, eave, x1 + 10, base)), wall, (0, 0, 0), 0.24, 30)
    tint(ic, ic.mask("rectangle", (x0, base - 80, x1, base)), wall, (26, 34, 18), 0.32, 20)
    roof = [(x0 - 50, eave + 18), (x1 + 40, eave + 18), (x1 - 14, ridge + 8), (x1 - 60, ridge - 4),
            (x0 + 40, ridge), (x0 + 8, ridge + 12)]
    rm = thatch(ic, roof, "#c0a56c", "#6e5430", course=46)
    tint(ic, ic.mask("rectangle", (x1 - 150, ridge, x1 + 50, eave + 30)), rm, (0, 0, 0), 0.22, 34)
    tint(ic, ic.mask("rectangle", (x0 - 60, ridge - 10, x0 + 160, ridge + 60)), rm, (255, 236, 200), 0.12, 30)
    ic.outline(roof, 7)
    tint(ic, ic.mask("rectangle", (x0, eave + 18, x1, eave + 76)), wall, (0, 0, 0), 0.55, 14)  # eave shadow
    # door and window
    ic.door(386, 610, 474, base - 2, arched=False, surround="#bcae94")
    ic.window(170, 600, 236, 660)
    tint(ic, ic.mask("rectangle", (150, 586, 256, 612)), None, (0, 0, 0), 0.3, 6)
    # lantern bracket by the door (the warden keeps the road at night)
    ic.line([(490, 592), (524, 592), (524, 610)], 7, IRON)
    ic.rect((510, 610, 538, 652), "#4e4a44", "#2a2826", edge=3)
    ic.rect((515, 617, 533, 646), "#6c6252", "#4a4236", edge=0)


def toll_bar(ic: Icon) -> None:
    """Swing-up toll bar: heavy post, pivot, banded pole raised over the road, stone counterweight."""
    px, pivot = 668, 590
    tint(ic, ic.poly_mask([(px + 8, RT + 10), (px + 46, RT + 10), (px + 112, RT + 44), (px + 72, RT + 48)]), None,
         (0, 0, 0), 0.3, 8)
    timber(ic, (px, RT + 22), (px, pivot - 76), 44, "#8e6646", "#4c3420")
    ic.poly([(px - 26, pivot - 82), (px, pivot - 110), (px + 26, pivot - 82)], "#7a5a3c", "#4c3420", edge=5)
    p_end = (px + 280, 228)
    ux, uy = p_end[0] - px, p_end[1] - pivot
    L = math.hypot(ux, uy)
    ux, uy = ux / L, uy / L
    back = (px - ux * 104, pivot - uy * 104)
    # the pole shades the heap below it
    tint(ic, ic.poly_mask([(px + 40, pivot + 30), (p_end[0] + 40, p_end[1] + 70), (p_end[0] + 60, p_end[1] + 100),
                           (px + 60, pivot + 70)]), None, (0, 0, 0), 0.22, 14)
    pole(ic, back, p_end, 48, n=6)
    # counterweight: a dark iron-strapped stone block clamped on the short end, clear of the wall
    nx, ny = -uy, ux  # across the pole

    def at(s: float, t: float):
        return (back[0] + ux * s + nx * t, back[1] + uy * s + ny * t)

    blk = [at(-44, -40), at(22, -40), at(22, 42), at(-44, 42)]
    bm = ic.poly_mask(blk)
    ic.fill(bm, "#6e675e", "#322e2a", (min(p[1] for p in blk), max(p[1] for p in blk)), noise=0.28, chroma=0.03)
    tint(ic, ic.poly_mask([at(-44, 8), at(22, 8), at(22, 42), at(-44, 42)]), bm, (0, 0, 0), 0.3, 4)
    for _ in range(5):  # chipped, weathered faces
        s, t = ic.random.uniform(-38, 16), ic.random.uniform(-34, 36)
        cx, cy = at(s, t)
        tint(ic, ic.mask("ellipse", (cx - 7, cy - 5, cx + 7, cy + 5)), bm, ic.random.choice([(0, 0, 0), (220, 210, 190)]),
             0.3, 2)
    ic.line([at(-44, 40), at(-44, -40), at(22, -40)], 6, (228, 218, 196, 215))  # lit short end and upper edge
    ic.line([at(-10, -40), at(-10, 42)], 7, IRON)  # iron strap round the block
    ic.outline(blk, 5, (30, 22, 16, 230))
    ic.draw.ellipse((px - 14, pivot - 14, px + 14, pivot + 14), fill=IRON + (255,))
    ic.draw.ellipse((px - 5, pivot - 5, px + 5, pivot + 5), fill=(130, 126, 118, 255))


def gravel(ic: Icon) -> None:
    """Gravel heap on the far verge with a shovel stuck in it."""
    tint(ic, ic.mask("ellipse", (670, RT - 26, 1014, RT + 30)), None, (0, 0, 0), 0.4, 12)
    mound(ic, 680, 1004, RT + 14, 560, body=("#b09470", "#5a4834"), pebble=11, peb_col=((240, 222, 190), (46, 34, 22)))
    timber(ic, (870, 590), (826, 420), 14, "#9a7450", "#5a3e26")  # shovel haft
    ic.poly([(862, 578), (900, 590), (894, 642), (870, 650), (854, 634)], "#76726a", "#3c3a36", edge=5)


def milestone(ic: Icon) -> None:
    """Squat cylindrical milestone on the near verge, leaning a little: weathered dark cap, one
    shaded number panel, lichen, a damp foot."""
    cx, base, w, h, ey, dome = 92, RF + 2, 122, 132, 18, 26
    tilt = -8.0
    hw = w / 2

    def rp(pts):  # local points (x across, y up = negative) -> leaning stone
        return ic.rotate(pts, (cx, base), tilt)

    tint(ic, ic.mask("ellipse", (cx - hw - 10, base - 20, cx + hw + 70, base + 18)), None, (0, 0, 0), 0.45, 10)
    arc_lo = [(hw * math.cos(a), ey * math.sin(a)) for a in np.linspace(0, math.pi, 18)]
    arc_hi = [(-hw * math.cos(a) * (1 - 0.06 * math.sin(a)), -h - (ey + dome) * math.sin(a) ** 0.8)
              for a in np.linspace(0, math.pi, 22)]
    body = rp(arc_lo + arc_hi)
    m = ic.poly_mask(body)
    xs = [p[0] for p in body]
    ic.fill(m, "#d4cab4", "#7a7162", (min(xs) + 10, max(xs) + 10), vertical=False, noise=0.22, chroma=0.05)
    # cylinder: specular band a third across, core shadow on the right
    tint(ic, ic.poly_mask(rp([(-hw * 0.55, -h), (-hw * 0.12, -h), (-hw * 0.12, 10), (-hw * 0.55, 10)])), m,
         (255, 248, 228), 0.3, 9)
    tint(ic, ic.poly_mask(rp([(hw * 0.3, -h - 30), (hw + 20, -h - 30), (hw + 20, 30), (hw * 0.3, 30)])), m, (0, 0, 0),
         0.34, 12)
    tint(ic, ic.poly_mask(rp([(-hw - 10, -40), (hw + 10, -40), (hw + 10, 30), (-hw - 10, 30)])), m, (40, 48, 28), 0.42, 12)
    # darker weathered cap
    front_arc = [(hw * math.cos(a), -h + ey * 0.7 * math.sin(a)) for a in np.linspace(0, math.pi, 18)]
    cap = rp(front_arc[::-1] + arc_hi[::-1])
    capm = ic.poly_mask(cap)
    ic.fill(capm, "#8a8272", "#4e4a42", (min(p[1] for p in cap), max(p[1] for p in cap) + 10), noise=0.34, chroma=0.05)
    tint(ic, ic.poly_mask(rp([(-hw * 0.8, -h - ey - dome), (-hw * 0.05, -h - ey - dome), (-hw * 0.2, -h),
                              (-hw * 0.8, -h)])), capm, (228, 220, 198), 0.24, 7)
    tint(ic, ic.poly_mask(rp([(hw * 0.2, -h - 40), (hw + 10, -h - 40), (hw + 10, -h + 20), (hw * 0.2, -h + 20)])), capm,
         (0, 0, 0), 0.3, 8)
    ic.line(rp(front_arc[1:-1]), 4, (40, 30, 22, 150))
    # one short recessed number panel
    pan = rp([(-30, -h + 36), (22, -h + 36), (22, -h + 72), (-30, -h + 72)])
    pm = ic.poly_mask(pan)
    tint(ic, pm, m, (46, 36, 26), 0.28)
    ic.line([pan[3], pan[0], pan[1]], 4, (44, 32, 22, 170))  # shaded top/left edge of the recess
    ic.line([pan[1], pan[2], pan[3]], 3, (250, 240, 220, 150))  # lit lower lip
    ic.line(rp([(-10, -h + 46), (-10, -h + 62)]), 6, (58, 46, 34, 170))  # a worn numeral stroke
    # lichen
    for lx, ly, r, col in ((-hw * 0.5, -h * 0.55, 16, (150, 158, 76)), (hw * 0.35, -h * 0.3, 13, (170, 172, 120)),
                           (-hw * 0.2, -h - 4, 12, (140, 150, 70)), (hw * 0.5, -22, 18, (110, 124, 58))):
        (qx, qy), = rp([(lx, ly)])
        tint(ic, ic.mask("ellipse", (qx - r, qy - r * 0.6, qx + r, qy + r * 0.6)), union(m, capm), col, 0.45, 3)
    ic.outline(body, 6)
    clump(ic, cx + hw - 8, base + 4, 52, 0.75)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    lodge(ic)
    gravel(ic)
    road(ic)
    tint(ic, ic.mask("rectangle", (90, RT - 4, 540, RT + 24)), None, (0, 0, 0), 0.35, 8)  # lodge contact
    verge_grass(ic)
    toll_bar(ic)
    milestone(ic)
