"""Paviors' Yard (paviors_yard): tier 1 of the road chain, a paving yard laying a sett road.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/paviors_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/paviors_yard

Identity: the road band in front is being paved: dressed granite setts in courses behind a pale
kerb, ending on the right in a raked sand bed with a string line and loose setts. Squared stacks
of setts, two upright wooden rammers (punners) and a sand heap stand before an open stone shed with
a tiled roof where the setts are dressed. Grows from the Road Wardens' Yard (earth track, thatched
lodge) and precedes the Macadam Works (crowned broken-stone road, roller).
Helpers: shared road-family block (``stones``, ``thatch``, ``timber``, ``planks``, ``weeds``,
``mound``, ``pole``), ``shingles`` (victualling_yard), new ``setts`` (paved courses),
``sett_stack`` and ``rammer``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 5
REFS = ("mason", "roads", "stone_quarry", "construction_center")

RT, RB, RF = 790, 900, 940  # road: back edge, front edge, foot of the kerb face
IRON = (44, 42, 40)
GRANITE = ((150, 148, 140), (92, 92, 90))

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


def setts(ic: Icon, clip: Image.Image, x0: float, x1: float, y0: float, y1: float, h0: float = 17, h1: float = 27,
          base=GRANITE[0], dark=GRANITE[1]) -> None:
    """Sett paving seen from the raised camera: courses deepen towards the viewer, every sett a small
    form (tone, lit top-left edge, dark bottom-right), dark sanded joints."""
    ic.fill(clip, base, dark, (y0, y1), noise=0.22, chroma=0.06)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0
    while y < y1:
        h = h0 + (h1 - h0) * (y - y0) / (y1 - y0)
        x = x0 - rnd(0, h * 2)
        while x < x1:
            w = h * rnd(1.6, 2.3)
            j = lambda: rnd(-2, 2)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 2 + j()),
                 (x + 3 + j(), y + h - 2 + j())]
            t = rnd(-1, 1)
            c = rnd(0, 1)
            if c < 0.12:
                d.polygon(q, fill=(150, 120, 90, 50))  # warmer stone
            elif c < 0.22:
                d.polygon(q, fill=(70, 80, 96, 50))  # bluish stone
            d.polygon(q, fill=(24, 18, 12, int(-t * 60)) if t < 0 else (255, 246, 230, int(t * 55)))
            d.line([q[3], q[0], q[1]], fill=(255, 248, 232, 110), width=3)
            d.line([q[1], q[2], q[3]], fill=(30, 26, 20, 150), width=4)
            d.line([(x + w, y), (x + w, y + h)], fill=(62, 54, 42, 210), width=4)
            x += w
        d.line([(x0, y + h), (x1, y + h)], fill=(62, 54, 42, 200), width=4)
        y += h
    paste_clipped(ic, lay, clip)


def sett_block(ic: Icon, x0: float, y0: float, x1: float, y1: float, tone: float = 1.0, lit: bool = False) -> None:
    """One dressed sett in a stack: lit face, dark lower-right edge, chipped arris."""
    warm = ic.random.random()
    k = (1.06, 1.0, 0.94) if warm < 0.2 else (0.95, 0.98, 1.06) if warm < 0.35 else (1, 1, 1)
    c1 = tuple(int(min(255, v * tone * f * (1.08 if lit else 1))) for v, f in zip(GRANITE[0], k))
    c2 = tuple(int(v * tone * f) for v, f in zip(GRANITE[1], k))
    m = ic.mask("rectangle", (x0 + 4, y0 + 4, x1 - 4, y1 - 3))
    ic.fill(m, c1, c2, (x0 - 20, x1 + 30), vertical=False, noise=0.22, chroma=0.08)
    ic.line([(x0 + 3, y1 - 4), (x0 + 3, y0 + 3), (x1 - 4, y0 + 3)], 3, (255, 248, 232, 110))
    ic.line([(x1 - 3, y0 + 4), (x1 - 3, y1 - 3), (x0 + 4, y1 - 3)], 4, (30, 26, 22, 170))


def cube(ic: Icon, d: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float, dx: float, dy: float,
         tone: float, lit: float = 1.0) -> list:
    """One sett as a small 3/4 cube on a layer: light top face, mid front, dark right side, chipped
    lit arris, thin dark joints. ``(x, y)`` is the front bottom-left corner. Returns the outline."""
    R = ic.random
    warm = R.random()
    k = (1.07, 1.0, 0.92) if warm < 0.2 else (0.94, 0.98, 1.07) if warm < 0.34 else (1, 1, 1)

    def col(base, f=1.0):
        return tuple(int(min(255, v * tone * kk * f)) for v, kk in zip(base, k)) + (255,)

    front = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]
    top = [(x, y - h), (x + w, y - h), (x + w + dx, y - h - dy), (x + dx, y - h - dy)]
    side = [(x + w, y), (x + w, y - h), (x + w + dx, y - h - dy), (x + w + dx, y - dy)]
    d.polygon(side, fill=col((96, 94, 90)))
    d.polygon(top, fill=col((204, 199, 186), lit))
    d.polygon(front, fill=col((146, 143, 134)))
    d.polygon([(x + w * 0.55, y), (x + w, y), (x + w, y - h), (x + w * 0.55, y - h)], fill=col((128, 125, 118)))
    d.line([(x + 3, y - 3), (x + w - 3, y - 3)], fill=(40, 34, 28, 120), width=4)  # dark lower lip
    d.line([(x + 2, y - h + 2), (x + w - 2, y - h + 2)], fill=(255, 250, 238, 170), width=3)  # lit arris
    outline = [(x, y), (x + w, y), (x + w + dx, y - dy), (x + w + dx, y - h - dy), (x + dx, y - h - dy), (x, y - h)]
    d.line(outline + [outline[0]], fill=(44, 38, 32, 200), width=3)
    d.line([(x, y - h), (x + w, y - h), (x + w + dx, y - h - dy)], fill=(44, 38, 32, 140), width=2)
    d.line([(x + w, y - h), (x + w, y)], fill=(44, 38, 32, 150), width=2)
    return outline


def sett_pile(ic: Icon, x0: float, base: float, cols: list[int], sw: float = 50, sh: float = 30, dx: float = 14,
              dy: float = 16) -> None:
    """Low, wide stack of setts built from 3/4 cubes: stepped columns so a lit top face shows on
    every step, dark right sides, contact shadow at the foot."""
    R = ic.random
    x1 = x0 + sw * len(cols) + dx
    tint(ic, ic.mask("ellipse", (x0 - 24, base - 22, x1 + 50, base + 18)), None, (0, 0, 0), 0.5, 10)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for r in range(max(cols)):  # bottom course first, left to right
        for i, n in enumerate(cols):
            if n > r:
                off = (R.uniform(-3, 3) if r else 0)
                cube(ic, d, x0 + i * sw + off, base - r * sh, sw - 2, sh - 2, dx, dy, R.uniform(0.78, 1.1),
                     lit=1.06 if i < len(cols) / 2 else 0.98)
    arr = np.asarray(lay).astype(float)
    arr[..., :3] *= (1 + 0.16 * ic.noise)[..., None]
    lay = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA")
    ic.image.alpha_composite(lay)
    m = lay.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, base - max(cols) * sh - dy, x1 + 10, base)), m,
         (0, 0, 0), 0.16, 24)


def rammer(ic: Icon, x: float, base: float, h: float, lean: float = 0.0, shadow: bool = True) -> None:
    """Pavior's rammer (punner): a fat, waisted wooden club about a third of the tool's height,
    iron hoops, a stout shaft and a cross-handle. ``lean`` in degrees (90 = lying, pointing right)."""
    def rot(pts):
        return ic.rotate(pts, (x, base), lean)

    bh, bw = h * 0.36, h * 0.13  # body length, half width
    if shadow:
        tint(ic, ic.mask("ellipse", (x - bw - 10, base - 14, x + bw + 60, base + 14)), None, (0, 0, 0), 0.5, 8)
    prof = []
    for f in np.linspace(0, 1, 12):  # waisted profile: full at foot and head, narrower in the middle
        prof.append((bw * (1 - 0.16 * math.sin(math.pi * f)), -bh * f))
    body_local = [(-px, py) for px, py in prof] + [(px, py) for px, py in prof[::-1]]
    body = rot(body_local)
    m = ic.poly_mask(body)
    lying = abs(lean) > 45
    xs, ys = [p[0] for p in body], [p[1] for p in body]
    ic.fill(m, "#a47c54", "#4e3420", (min(ys), max(ys)) if lying else (min(xs), max(xs)), vertical=lying,
            noise=0.22, chroma=0.06)
    # round form: highlight a third across on the lit side, core shadow on the far side, grain
    tint(ic, ic.poly_mask(rot([(-bw * 0.62, 4), (-bw * 0.18, 4), (-bw * 0.18, -bh - 4), (-bw * 0.62, -bh - 4)])), m,
         (255, 232, 196), 0.3, 6)
    tint(ic, ic.poly_mask(rot([(bw * 0.3, 4), (bw * 1.2, 4), (bw * 1.2, -bh - 4), (bw * 0.3, -bh - 4)])), m,
         (12, 6, 2), 0.42, 7)
    for gx in (-bw * 0.4, bw * 0.05, bw * 0.45):
        ic.line(rot([(gx, -bh * 0.1), (gx * 0.9, -bh * 0.9)]), 2, (50, 30, 16, 80))
    for f in (0.07, 0.93):  # iron hoops
        a, b = rot([(-bw * (1 - 0.03), -bh * f), (bw * (1 - 0.03), -bh * f)])
        ic.line([a, b], 10, (58, 56, 54))
        ic.line(rot([(-bw * 0.9, -bh * f - 3), (-bw * 0.1, -bh * f - 3)]), 3, (170, 164, 154, 160))
    ic.outline(body, 4, (40, 26, 16, 200))
    a, b = rot([(0, -bh + 2), (0, -h)])
    timber(ic, a, b, 18, "#a07a54", "#5a3e26")
    c, e = rot([(-40, -h + 8), (40, -h + 8)])
    timber(ic, c, e, 17, "#a07a54", "#5a3e26")


def shed(ic: Icon) -> None:
    """Open stone dressing shed: ashlar piers, heavy lintel, tiled roof; a banker with a sett in
    the light, rough blocks inside in the shade."""
    x0, x1, eave, ridge, base = 40, 450, 500, 214, RT + 4
    inner = ic.mask("rectangle", (x0 + 20, eave, x1 - 20, base))
    ic.fill(inner, "#3a3026", "#1c1610", (eave, base), noise=0.12)
    with ic.clipped(inner):
        stones(ic, (x0, eave, x1, base), "#5c5246", "#2e281f", course=36, lit=30, shadow=90, moss=0.0)
        tint(ic, ic.mask("rectangle", (x0, eave, x1, eave + 120)), None, (0, 0, 0), 0.5, 20)
        for bx, by, bw, bh in ((290, 730, 70, 58), (350, 744, 44, 44), (310, 686, 60, 44)):
            ic.rock(ic.jitter(bx + bw / 2, by + bh / 2, bw / 2, bh / 2, 7, 0.12), "#8a847a", "#4a4640", facets=2)
        ic.shade(inner, (0, 0, 0), 0.25)
        # banker: a stout bench at the front of the bay, a sett on it catching the light
        ic.rect((92, 700, 232, 726), "#9a8e78", "#645a4a", edge=4)
        ic.line([(96, 703), (228, 703)], 4, (255, 246, 226, 120))
        ic.rect((104, 726, 124, base), "#6a6052", "#403a32", edge=3)
        ic.rect((200, 726, 220, base), "#6a6052", "#403a32", edge=3)
        lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        cube(ic, ImageDraw.Draw(lay), 128, 700, 56, 38, 16, 18, 0.92, lit=1.08)
        ic.image.alpha_composite(lay)
        tint(ic, ic.mask("ellipse", (96, 640, 220, 700)), None, (255, 240, 210), 0.1, 16)  # light falling on it
        ic.line([(196, 692), (218, 668)], 6, (60, 58, 54))  # chisel
    for px0, px1 in ((x0, x0 + 56), (232, 274), (x1 - 56, x1)):  # ashlar piers
        stones(ic, (px0, eave, px1, base), "#c2b396", "#80735c", course=40, moss=0.08)
        ic.outline([(px0, eave), (px1, eave), (px1, base), (px0, base)], 5)
        tint(ic, ic.mask("rectangle", ((px0 + px1) / 2 + 4, eave, px1, base)), None, (0, 0, 0), 0.18, 4)
    timber(ic, (x0 - 6, eave + 16), (x1 + 6, eave + 16), 34, "#8e6848", "#4e3522")
    roof = [(x0 - 44, eave + 4), (x1 + 44, eave + 4), (x1 - 80, ridge), (x0 + 80, ridge)]
    rm = shingles(ic, roof, "#a8664a", "#5e3424", course=34, stagger=44, edge=7)
    tint(ic, ic.mask("rectangle", (x1 - 180, ridge, x1 + 60, eave + 10)), rm, (0, 0, 0), 0.22, 40)
    tint(ic, ic.mask("rectangle", (x0 - 50, ridge, x0 + 170, ridge + 90)), rm, (255, 230, 200), 0.1, 30)
    ic.rect((x0 + 74, ridge - 18, x1 - 74, ridge + 4), "#8a4e38", "#5a3222", edge=5)  # ridge tiles
    tint(ic, ic.mask("rectangle", (x0 - 10, eave + 30, x1 + 10, eave + 80)), None, (0, 0, 0), 0.4, 12)


def fan_setts(ic: Icon, clip: Image.Image, x0: float, x1: float, y0: float, y1: float, h0: float = 15,
              h1: float = 24, unit: float = 170, amp: float = 9) -> None:
    """Setts laid in segmental arcs (fan paving) seen from the raised camera: every course bows
    towards the back within each fan unit, joints lean towards the unit's centre, every sett its own
    tone, dark sanded joints."""
    ic.fill(clip, (72, 66, 56), (52, 46, 38), (y0, y1), noise=0.2)
    R = ic.random

    def bump(x: float) -> float:
        u = ((x - x0) % unit) / unit * 2 - 1
        return 1 - u * u

    def cy(y: float, x: float) -> float:
        return y - amp * bump(x) * (0.6 + 0.4 * (y - y0) / (y1 - y0))

    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = y0 - amp
    while y < y1 + amp:
        h = h0 + (h1 - h0) * max(0.0, (y - y0)) / (y1 - y0)
        x = x0 - R.uniform(0, h * 2)
        while x < x1:
            w = h * R.uniform(1.25, 1.7)
            xa, xb = x + 2.5, x + w - 2.5
            ua = ((xa - x0) % unit) / unit * 2 - 1
            lean = -ua * 4  # joints lean towards the fan centre
            xm = (xa + xb) / 2
            q = [(xa, cy(y + 2.5, xa)), (xm, cy(y + 2.5, xm)), (xb, cy(y + 2.5, xb)),
                 (xb + lean, cy(y + h - 2, xb)), (xm + lean, cy(y + h - 2, xm)), (xa + lean, cy(y + h - 2, xa))]
            t = R.uniform(0.76, 1.16)
            c = R.random()
            base = (164, 160, 150) if c > 0.3 else (176, 158, 136) if c > 0.15 else (140, 148, 160)
            d.polygon(q, fill=tuple(int(min(255, v * t)) for v in base) + (255,))
            d.line([q[5], q[0], q[1], q[2]], fill=(255, 250, 236, 120), width=3)
            d.line([q[2], q[3], q[4], q[5]], fill=(34, 28, 22, 130), width=3)
            x += w
        y += h
    arr = np.asarray(lay).astype(float)
    arr[..., :3] *= (1 + 0.18 * ic.noise)[..., None]
    paste_clipped(ic, Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA"), clip)


def road(ic: Icon) -> None:
    """Fan-paved sett road behind a pale kerb; on the right the raked sand bed still waiting for its
    setts, with a string line and loose setts."""
    top = [(54, RT), (970, RT), (1010, RB), (14, RB)]
    tm = ic.poly_mask(top)
    KB = RB - 20  # back edge of the kerb's top face
    edge = []
    y = RT
    while y < KB:
        edge.append((630 + ic.random.uniform(-26, 26) + (y - RT) * 0.3, y))
        y += 18
    paved = ic.intersect(tm, ic.poly_mask([(0, RT - 5), *edge, (660, KB), (0, KB)]))
    bed = ic.intersect(tm, ImageChops.invert(paved), ic.mask("rectangle", (0, 0, 1024, KB)))
    ic.fill(bed, "#c8ad7c", "#98805a", (RT, KB), noise=0.3)
    for i, yy in enumerate((RT + 16, RT + 38, RT + 60)):  # soft rake grooves
        g = [(x, yy + 3 * math.sin(x / 60 + i)) for x in np.linspace(600, 1020, 24)]
        gm, lm = Image.new("L", (ic.size, ic.size), 0), Image.new("L", (ic.size, ic.size), 0)
        ImageDraw.Draw(gm).line(g, fill=255, width=7)
        ImageDraw.Draw(lm).line([(x, y + 7) for x, y in g], fill=255, width=5)
        tint(ic, gm, bed, (70, 50, 28), 0.45, 3)
        tint(ic, lm, bed, (255, 240, 205), 0.3, 2)
    fan_setts(ic, paved, 14, 720, RT, KB)
    tint(ic, ic.mask("rectangle", (0, RT, 1024, RT + 14)), tm, (0, 0, 0), 0.25, 6)
    # loose setts on the bed and the string line with its peg
    for sx, sy in ((664, RT + 14), (650, RT + 52)):
        sett_block(ic, sx, sy, sx + 42, sy + 26, tone=ic.random.uniform(0.9, 1.05), lit=True)
    ic.line([(650, RT + 10), (990, RT + 16)], 3, (236, 230, 214, 230))
    timber(ic, (990, RT + 26), (992, RT - 12), 10, "#9a7450", "#5a3e26")
    # pale dressed kerb: a distinct light top strip with its own shadow line, then the front face
    km = ic.intersect(tm, ic.mask("rectangle", (0, KB, 1024, RB + 1)))
    ic.fill(km, "#e2d8c2", "#b8ad96", (KB, RB), noise=0.18, chroma=0.04)
    x = 14
    while x < 1010:
        x += ic.random.uniform(110, 160)
        ic.line([(x, KB + 2), (x + 3, RB)], 3, (70, 62, 50, 170))
    tint(ic, ic.mask("rectangle", (0, KB - 8, 1024, KB + 2)), tm, (20, 14, 8), 0.6, 3)  # shadow line behind the kerb
    ic.line([(20, KB + 4), (1004, KB + 4)], 3, (255, 250, 236, 160))
    face = [(14, RB), (1010, RB), (1004, RF), (20, RF)]
    fm = ic.poly_mask(face)
    stones(ic, (14, RB, 1010, RF), "#c2b69e", "#7e7462", course=46, clip=fm, lit=90, moss=0.04)
    tint(ic, ic.mask("rectangle", (0, RB, 1024, RB + 10)), fm, (0, 0, 0), 0.3, 4)
    ic.outline(top[:2] + [top[2], (1004, RF), (20, RF), top[3]], 6)


def sand_bed(ic: Icon) -> None:
    """Low, flat-topped bed of bedding sand with rake lines across its top, on the far side."""
    x0, x1, base, top_f, top_b = 812, 1016, RT + 8, RT - 64, RT - 92
    tint(ic, ic.mask("ellipse", (x0 - 20, base - 24, x1 + 20, base + 20)), None, (0, 0, 0), 0.45, 12)
    topf = [(x0 + 30, top_b + 2), (x1 - 34, top_b - 2), (x1 - 12, top_f), (x0 + 18, top_f + 3)]
    slope = [(x0 + 18, top_f + 3), (x1 - 12, top_f), (x1, base), (x0, base)]
    sm = ic.poly_mask(slope)
    ic.fill(sm, "#bd9c68", "#7c603a", (top_f, base), noise=0.3, chroma=0.08)
    tint(ic, ic.mask("rectangle", (x1 - 90, top_f, x1 + 10, base)), sm, (0, 0, 0), 0.3, 24)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for _ in range(120):
        gx, gy = ic.random.uniform(x0, x1), ic.random.uniform(top_f, base)
        d.ellipse((gx - 3, gy - 2, gx + 3, gy + 2), fill=(250, 234, 196, 120) if ic.random.random() < 0.5 else (90, 66, 36, 110))
    paste_clipped(ic, lay, sm)
    tm = ic.poly_mask(topf)
    ic.fill(tm, "#e0c690", "#c4a672", (top_b, top_f), noise=0.22, chroma=0.06)
    for i in range(5):  # rake lines along the top
        f = (i + 0.6) / 5.4
        yb, yf = top_b + (top_f - top_b) * f, top_b + (top_f - top_b) * f
        ic.line([(x0 + 30 - 12 * f, yb), (x1 - 34 + 22 * f, yf - 2)], 3, (120, 90, 52, 150))
        ic.line([(x0 + 30 - 12 * f, yb + 3), (x1 - 34 + 22 * f, yf + 1)], 2, (255, 244, 214, 120))
    ic.outline(topf[:2] + [slope[1], slope[2], slope[3], slope[0]], 5)
    ic.line([topf[3], topf[2]], 3, (90, 66, 40, 150))
    # a hand rake lying across the bed
    timber(ic, (826, top_f - 8), (986, top_b + 4), 9, "#a07a54", "#5a3e26")
    ic.line([(978, top_b - 10), (1000, top_b + 22)], 8, (58, 56, 54))


def shear_legs(ic: Icon) -> None:
    """Timber shear legs over the sand bed lifting a kerbstone on a chain."""
    ax, ay = 912, 408
    timber(ic, (952, RT - 70), (ax + 4, ay + 10), 16, "#6e5238", "#3e2c1c")  # far leg, in shade
    ky = 588
    ic.line([(ax, ay + 20), (ax + 2, ky - 22)], 6, (50, 48, 46))
    ic.line([(ax - 4, ay + 20), (ax - 2, ky - 22)], 2, (150, 144, 136, 150))
    kb = (ax - 84, ky, ax + 84, ky + 54)
    ic.line([(ax, ky - 26), (kb[0] + 16, kb[1] - 12)], 5, (50, 48, 46))
    ic.line([(ax, ky - 26), (kb[2] - 16, kb[1] - 12)], 5, (50, 48, 46))
    q = [(kb[0], kb[1]), (kb[2], kb[1]), (kb[2] + 8, kb[1] - 16), (kb[0] + 8, kb[1] - 16)]
    ic.fill(ic.poly_mask(q), "#e4dcc8", "#b0a692", noise=0.18)
    stones(ic, kb, "#cfc6b0", "#8e8470", course=60, lit=90, moss=0.0)
    sq = [(kb[2], kb[1]), (kb[2] + 8, kb[1] - 16), (kb[2] + 8, kb[3] - 16), (kb[2], kb[3])]
    ic.fill(ic.poly_mask(sq), "#7e7462", "#5a5244", noise=0.18)
    ic.outline([(kb[0], kb[1] - 16), (kb[2] + 8, kb[1] - 16), (kb[2] + 8, kb[3] - 16), (kb[2], kb[3]), (kb[0], kb[3])], 5)
    tint(ic, ic.mask("ellipse", (kb[0] + 10, RT - 110, kb[2] + 40, RT - 70)), None, (0, 0, 0), 0.25, 12)
    timber(ic, (838, RT - 4), (ax, ay), 20, "#9a7450", "#5a3e26")
    timber(ic, (1004, RT + 2), (ax + 6, ay), 20, "#8e6a48", "#523a24")
    ic.draw.ellipse((ax - 16, ay - 12, ax + 16, ay + 20), fill=(52, 48, 44, 255))
    ic.draw.ellipse((ax - 6, ay - 2, ax + 6, ay + 10), fill=(120, 114, 106, 255))


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    shed(ic)
    sand_bed(ic)
    shear_legs(ic)
    sett_pile(ic, 500, RT + 6, [2, 3, 3, 2], sw=52, sh=34, dx=16, dy=18)
    sett_pile(ic, 764, RT + 2, [2, 1], sw=50, sh=32, dx=16, dy=18)
    rammer(ic, 494, RT + 12, 322, lean=-10)  # leaning against the shed pier
    road(ic)
    tint(ic, ic.mask("rectangle", (30, RT - 6, 460, RT + 20)), None, (0, 0, 0), 0.35, 8)
    tint(ic, ic.mask("ellipse", (700, RT + 34, 960, RT + 74)), None, (0, 0, 0), 0.4, 8)
    rammer(ic, 716, RT + 46, 240, lean=88, shadow=False)  # laid down on the bed
