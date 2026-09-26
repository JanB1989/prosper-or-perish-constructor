"""Jiangnan Canal Network (jiangnan_canal_network): a water-town canal with a humped arch bridge.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the steep single-arch stone bridge whose arch and its reflection close into a ring, and
beside it whitewashed canal houses with dark tile caps and stepped horse-head gables, standing on
granite footings straight out of the water with steps down to it. A smaller house stands behind the far
ramp, a small black-awning boat is moored at the houses. Unlike the vanilla bridge (towers, twin arches)
this is a single high hump in a Jiangnan water town.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

# ---- waterways family palette (shared with canal_lock_works) ------------------------------------
STONE, STONE_DK = "#a08a70", "#665646"
KERB, KERB_DK = "#c2ae90", "#94806a"
W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
WOOD, WOOD_DK = "#86603e", "#4e3522"
GRASS, GRASS_DK = "#86924f", "#4c5a2a"


# ---- helpers (candidates for the kit) ----------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*ms: Image.Image) -> Image.Image:
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def minus(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def band(ic: Icon, top: float, bottom: float, x0: float = 18, x1: float = 1006, inset: float = 40,
         sag: float = 30) -> Image.Image:
    """Vanilla water stage at the front, in the family's water colours."""
    return ic.water_band(top=top, bottom=bottom, x0=x0, x1=x1, inset=inset, sag=sag, light=W_LIGHT, deep=W_DEEP)


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(36, 52), width=(70, 150), moss=True,
           clip: Image.Image | None = None) -> None:
    """Weathered ashlar face: per-block tint, soft bevels (lit top/left, dark bottom/right), faint
    mortar, grime streaks from the top, darker damp base with moss. No hard outline per block."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    if clip is not None:
        m = ic.intersect(m, clip)
    ic.fill(m, base, dark, (x0 - 200, x1 + 200), vertical=False, noise=0.22, chroma=0.14)
    R = ic.random
    lay, d = layer()
    y = y0
    while y < y1:
        yb = min(y + R.randint(*course), y1)
        x = x0 - R.randint(0, width[0])
        while x < x1:
            xb = x + R.randint(*width)
            bx0, bx1 = max(x, x0), min(xb, x1)
            if bx1 - bx0 > 8:
                t = R.uniform(-1, 1)
                d.rectangle((bx0, y, bx1, yb), fill=(255, 240, 215, int(34 * t)) if t > 0 else (30, 22, 14, int(-52 * t)))
                d.line([(bx0 + 4, y + 4), (bx1 - 5, y + 4)], fill=(255, 246, 228, 70), width=4)
                d.line([(bx0 + 4, y + 4), (bx0 + 4, yb - 5)], fill=(255, 246, 228, 40), width=3)
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
                if R.random() < 0.18:
                    cx, cy = (bx0 + 6, yb - 6) if R.random() < 0.5 else (bx1 - 6, y + 6)
                    d.ellipse((cx - 7, cy - 6, cx + 7, cy + 6), fill=(40, 30, 22, 90))
            x = xb
        y = yb
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 55)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.25, 0.7) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 14), y0, sx + R.uniform(5, 14), y0 + ln))),
                 (35, 30, 22), R.uniform(0.10, 0.2), blur=6)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - min(110, (y1 - y0) * 0.6), x1, y1 + 40))), (22, 30, 20),
             0.42, blur=22)
    if moss:
        for _ in range(int((x1 - x0) / 40)):
            mx = R.uniform(x0, x1)
            my = y1 - R.uniform(10, min(90, (y1 - y0) * 0.6))
            blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(14, 36), R.uniform(8, 18), 8, 0.3)))
            ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)


def kerb(ic: Icon, x0: float, x1: float, top: float, face: float, lip: float = 16) -> None:
    """Coping stones along a wall head: lit top strip, darker front edge, cast shadow under the lip."""
    R = ic.random
    mid = top + (face - top) * 0.45
    ic.fill(ic.mask("rectangle", (x0, top, x1, mid)), KERB, "#ab987c", (x0, x1), vertical=False, noise=0.18)
    ic.fill(ic.mask("rectangle", (x0, mid, x1, face)), "#98826a", "#6e5c4a", (mid, face), noise=0.2)
    x = x0 + R.randint(20, 90)
    while x < x1 - 20:
        ic.line([(x, top + 2), (x, face - 2)], 3, (50, 40, 30, 120))
        x += R.randint(90, 170)
    ic.line([(x0, mid), (x1, mid)], 3, (255, 244, 222, 80))
    if lip:
        ic.shade(ic.mask("rectangle", (x0, face, x1, face + lip)), alpha=0.45, blur=7)


def ripples(ic: Icon, m: Image.Image, y0: float, y1: float, x0: float, x1: float, density: float = 2600) -> None:
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / density)):
        y = R.uniform(y0, y1)
        x = R.uniform(x0 - 20, x1)
        L = R.uniform(30, 80)
        d.line([(x, y), (x + L, y)], fill=(222, 238, 240, R.randint(90, 160)), width=4)
        d.line([(x + 10, y + 6), (x + L - 6, y + 6)], fill=(20, 45, 58, 90), width=3)
    composite(ic, lay, m)


def water_poly(ic: Icon, pts, reflect: float = 0, span=None, light=W_LIGHT, deep=W_DEEP,
               density: float = 2600) -> Image.Image:
    """Open water surface of any shape seen from the raised camera; lighter far edge, ripples."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    y0, y1 = span or (min(ys) - 10, max(ys) + 20)
    ic.fill(m, light, deep, (y0, y1), noise=0.08, chroma=0.06)
    if reflect:
        ic.shade(ic.intersect(m, ic.mask("rectangle", (0, min(ys), SIZE, min(ys) + reflect))), (30, 42, 40), 0.35, blur=8)
    ripples(ic, m, min(ys) + reflect * 0.8, max(ys) - 6, min(xs), max(xs), density)
    return m


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, vertical_boards: bool = True) -> Image.Image:
    """Board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    lo, hi = (min(xs), max(xs)) if vertical_boards else (min(ys), max(ys))
    v = lo
    while v < hi:
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        col = (255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t))
        if vertical_boards:
            d.rectangle((v, min(ys), v + w, max(ys)), fill=col)
            for _ in range(2):
                gx = v + R.uniform(4, max(5, w - 4))
                d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        else:
            d.rectangle((min(xs), v, max(xs), v + w), fill=col)
            gy = v + R.uniform(4, max(5, w - 4))
            d.line([(min(xs), gy), (max(xs), gy + R.uniform(-3, 3))], fill=(40, 24, 12, 60), width=2)
            d.line([(min(xs), v), (max(xs), v)], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
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
    ic.shade(ic.poly_mask(lower), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def pile(ic: Icon, x: float, top: float, bottom: float, w: float = 30, c1="#8a6a4a", c2="#4a3624") -> None:
    """Round timber pile seen from the side: lit left, dark right, weathered top ellipse."""
    m = ic.mask("rectangle", (x - w / 2, top, x + w / 2, bottom))
    ic.fill(m, c1, c2, (x - w / 2, x + w / 2), vertical=False, noise=0.2)
    ic.line([(x - w * 0.22, top + 6), (x - w * 0.22, bottom)], 3, (255, 230, 190, 60))
    ic.fill(ic.mask("ellipse", (x - w / 2, top - w * 0.28, x + w / 2, top + w * 0.28)), "#b89a78", "#7a6048",
            radial=(x - w * 0.2, top - 4, w * 0.6), noise=0.2)
    ic.overlay(lambda d: d.ellipse((x - w / 2, top - w * 0.28, x + w / 2, top + w * 0.28), outline=(40, 28, 18, 170), width=3))
    ic.overlay(lambda d: d.rectangle((x - w / 2, top, x + w / 2, bottom), outline=(40, 28, 18, 150), width=3))


def spout(ic: Icon, x: float, y: float, dx: float, dy: float, w: float = 16) -> None:
    """Water jet leaving an opening at (x, y), arcing by (dx, dy), with a splash where it lands."""
    ts = np.linspace(0, 1, 18)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    lay, d = layer()
    d.line(path, fill=(170, 210, 220, 230), width=int(w + 8), joint="curve")
    d.line(path, fill=(236, 246, 247, 240), width=int(w), joint="curve")
    d.line([(px - 2, py - w * 0.2) for px, py in path[2:]], fill=(255, 255, 255, 170), width=max(3, int(w * 0.3)))
    ex, ey = path[-1]
    for _ in range(12):
        r = ic.random.uniform(4, 10)
        sx, sy = ex + ic.random.uniform(-w * 2.2, w * 2.2), ey + ic.random.uniform(-w * 1.2, w * 0.4)
        d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(240, 248, 248, 210))
    d.ellipse((ex - w * 2.6, ey - w * 0.5, ex + w * 2.6, ey + w * 0.7), fill=(232, 244, 245, 200))
    ic.image.alpha_composite(lay)


def splash(ic: Icon, x0: float, x1: float, y: float, clip: Image.Image | None = None, n: int = 16) -> None:
    lay, d = layer()
    for _ in range(n):
        r = ic.random.uniform(7, 14)
        sx, sy = ic.random.uniform(x0, x1), y + ic.random.uniform(-12, 16)
        d.ellipse((sx - r * 1.6, sy - r * 0.6, sx + r * 1.6, sy + r * 0.6), fill=(240, 248, 248, 220))
    composite(ic, lay, clip)


def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float, light="#7a8c4c", dark="#2f3f1e", n: int = 16) -> Image.Image:
    """Tree crown as one massed shape (union of lumps) with form shading; no outlines inside."""
    R = ic.random
    m = blank()
    lumps = []
    for _ in range(n):
        a = R.uniform(0, 2 * math.pi)
        d = R.uniform(0.0, 0.6) ** 0.8
        bx, by = cx + math.cos(a) * rx * d, cy + math.sin(a) * ry * d
        br = min(rx, ry) * R.uniform(0.45, 0.62)
        lumps.append((bx, by, br))
        m = ImageChops.lighter(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.85, 14, 0.07)))
    ic.fill(m, light, dark, radial=(cx - rx * 0.6, cy - ry * 0.7, max(rx, ry) * 2.0), noise=0.3, chroma=0.16)
    for bx, by, br in lumps:
        cap = ic.poly_mask(ic.jitter(bx - br * 0.25, by - br * 0.3, br * 0.6, br * 0.45, 8, 0.25))
        ic.shade(ic.intersect(cap, m), (220, 235, 150), 0.16, blur=3)
        under = ic.poly_mask(ic.jitter(bx + br * 0.2, by + br * 0.45, br * 0.8, br * 0.35, 8, 0.25))
        ic.shade(ic.intersect(under, m), (8, 18, 6), 0.3, blur=5)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 0.1, cy - ry * 0.1, cx + rx * 1.4, cy + ry * 1.3))),
             (8, 16, 6), 0.3, blur=20)
    return m


def weeds(ic: Icon, x: float, y: float, w: float, hang: bool = True) -> None:
    """Tuft of grass and weeds on a coping, a few blades hanging over the wall face."""
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 34)
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.9 if down else -h))
        col = (R.randint(90, 130), R.randint(110, 140), R.randint(50, 70), 230)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


def turf(ic: Icon, m: Image.Image, light=GRASS, dark=GRASS_DK, span=None, density: float = 420) -> None:
    """Grass-covered earth: gradient, short blade strokes lit and shadowed, a few darker patches."""
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, light, dark, span or (y0, y1), noise=0.3, chroma=0.14)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / density)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        h = R.uniform(8, 20)
        t = R.uniform(-1, 1)
        col = (228, 236, 170, int(60 * t)) if t > 0 else (18, 28, 8, int(-80 * t))
        d.line([(x, y), (x + R.uniform(-5, 5), y - h)], fill=col, width=3)
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 70)):
        bx, by = R.uniform(x0, x1), R.uniform(y0, y1)
        blob = ic.poly_mask(ic.jitter(bx, by, R.uniform(30, 70), R.uniform(12, 26), 8, 0.3))
        ic.shade(ic.intersect(blob, m), (30, 40, 14) if R.random() < 0.6 else (200, 190, 120), R.uniform(0.1, 0.22), blur=10)


def earth(ic: Icon, m: Image.Image, light="#a88a60", dark="#6a5238", span=None) -> None:
    """Bare earth or mud: gradient, clods and small stones."""
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, light, dark, span or (y0, y1), noise=0.32, chroma=0.12)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / 900)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        r = R.uniform(3, 9)
        d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(40, 28, 16, R.randint(40, 90)))
        d.line([(x - r * 0.7, y - r * 0.5), (x + r * 0.3, y - r * 0.6)], fill=(255, 236, 200, 60), width=2)
    composite(ic, lay, m)


def reeds(ic: Icon, x0: float, x1: float, base: float, h: float, n: int | None = None, heads: float = 0.25,
          clip: Image.Image | None = None) -> None:
    """Reed bed: thin leaning blades in several greens and straw tones, some with dark cattail heads."""
    R = ic.random
    lay, d = layer()
    n = n or int((x1 - x0) / 6)
    items = sorted(((R.uniform(x0, x1), R.uniform(0.45, 1.0), R.uniform(-4, 10)) for _ in range(n)), key=lambda t: t[1])
    for x, f, dy in items:
        hh = h * f
        lean = R.uniform(-0.3, 0.3) * hh
        b = (x, base + dy)
        mid = (x + lean * 0.35, base + dy - hh * 0.55)
        tip = (x + lean, base + dy - hh)
        k = R.random()
        col = (int(80 + 70 * k), int(104 + 40 * k), int(44 + 20 * k)) if R.random() < 0.8 else (170, 150, 90)
        shade = f * 0.6 + 0.4
        dark = tuple(int(v * 0.5) for v in col)
        d.line([b, mid, tip], fill=dark + (255,), width=8, joint="curve")
        d.line([(b[0] - 1, b[1]), (mid[0] - 2, mid[1]), (tip[0] - 1, tip[1])],
               fill=tuple(int(min(255, v * shade)) for v in col) + (255,), width=4, joint="curve")
        if R.random() < heads:
            hx, hy = x + lean * 0.8, base + dy - hh * 0.8
            d.ellipse((hx - 7, hy - 18, hx + 7, hy + 18), fill=(84, 54, 32, 255), outline=(40, 26, 16, 255), width=3)
            d.ellipse((hx - 4, hy - 13, hx + 1, hy + 4), fill=(140, 100, 64, 200))
    composite(ic, lay, clip)


def bricks(ic: Icon, m: Image.Image, box, base="#9a5e46", dark="#5c3628", course: float = 18, length: float = 42) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay, d = layer()
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:
                col = (40, 22, 18, 90)
            else:
                col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(210, 190, 160, 60), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(210, 190, 160, 70), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    composite(ic, lay, m)


def plaster(ic: Icon, m: Image.Image, light="#e4dccb", dark="#b3aa98", span=None) -> None:
    """Whitewashed wall: warm off-white, blotchy wash, grime streaks, damp darker foot."""
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, light, dark, span or (y0, y1), noise=0.14, chroma=0.06)
    R = ic.random
    for _ in range(int((x1 - x0) / 45)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.2, 0.6) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(4, 12), y0, sx + R.uniform(4, 12), y0 + ln))),
                 (60, 56, 50), R.uniform(0.08, 0.16), blur=6)
    for _ in range(int((x1 - x0) / 90)):
        bx, by = R.uniform(x0, x1), R.uniform(y0, y1)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(bx, by, R.uniform(20, 40), R.uniform(10, 24), 8, 0.3))),
                 (120, 110, 96), R.uniform(0.12, 0.25), blur=5)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - (y1 - y0) * 0.3, x1, y1))), (40, 50, 36), 0.35, blur=18)


def frond(ic: Icon, base, deg: float, L: float, droop: float = 0.55, colors=("#86984c", "#2c4016")) -> None:
    """Palm frond: arched rachis with drooping leaflets on both sides, massed and shaded."""
    a = math.radians(deg)
    dx, dy = math.cos(a), math.sin(a)
    bx, by = base
    n = 26
    ts = np.linspace(0, 1, n)
    spine = [(bx + dx * L * t, by + dy * L * t + droop * L * t * t) for t in ts]
    W = L * 0.17
    side1, side2 = [], []
    for i, t in enumerate(ts):
        px, py = spine[i]
        qx, qy = spine[min(i + 1, n - 1)] if i < n - 1 else spine[i]
        ox, oy = spine[max(i - 1, 0)]
        tx, ty = qx - ox, qy - oy
        tl = math.hypot(tx, ty) or 1
        tx, ty = tx / tl, ty / tl
        nx, ny = -ty, tx
        w = W * math.sin(math.pi * min(t, 0.98)) ** 0.6
        cut = 0.35 if i % 2 else 1.0  # serrated edge: leaflet tips and notches
        back = -L * 0.03 if i % 2 else 0
        side1.append((px + nx * w * cut + tx * back, py + ny * w * cut + ty * back + (w * 0.5 if i % 2 == 0 else 0)))
        side2.append((px - nx * w * cut + tx * back, py - ny * w * cut + ty * back + (w * 0.5 if i % 2 == 0 else 0)))
    pts = side1 + side2[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], radial=(bx - L * 0.2, by - L * 0.3, L * 1.3), noise=0.3, chroma=0.14)
    lower = side2 if dx >= 0 else side1
    ic.shade(ic.intersect(m, ic.poly_mask(spine + lower[::-1])), (10, 20, 5), 0.3)
    ic.line(spine[:-2], 4, (170, 170, 100, 200))
    ic.outline(pts, 3, (30, 40, 14, 170))


def palm(ic: Icon, x: float, base: float, tx: float, ty: float, crown: float, w: float = 34) -> None:
    """Date palm: curved ringed trunk, crown of drooping fronds, date clusters under the crown."""
    ts = np.linspace(0, 1, 30)
    cx, cy = x + (tx - x) * 0.15, base - (base - ty) * 0.55
    path = [((1 - t) ** 2 * x + 2 * (1 - t) * t * cx + t * t * tx, (1 - t) ** 2 * base + 2 * (1 - t) * t * cy + t * t * ty)
            for t in ts]
    left, right = [], []
    for i, (px, py) in enumerate(path):
        q = path[min(i + 1, len(path) - 1)] if i < len(path) - 1 else path[i]
        p0 = path[max(i - 1, 0)]
        vx, vy = q[0] - p0[0], q[1] - p0[1]
        vl = math.hypot(vx, vy) or 1
        nx, ny = -vy / vl, vx / vl
        hw = w * (1.0 - 0.35 * ts[i]) / 2
        left.append((px - nx * hw, py - ny * hw))
        right.append((px + nx * hw, py + ny * hw))
    pts = left + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, "#9a8264", "#4e3c28", (x - w, x + w), vertical=False, noise=0.25)
    ic.shade(ic.intersect(m, ic.poly_mask(path + right[::-1])), (20, 12, 6), 0.35)
    for i in range(1, len(path) - 1, 2):
        ic.line([left[i], right[i]], 4, (50, 36, 22, 170))
        ic.line([(left[i][0], left[i][1] - 4), (right[i][0], right[i][1] - 4)], 2, (220, 200, 160, 70))
    ic.outline(pts, 4, (40, 28, 18, 170))
    R = ic.random
    for ddx in (-24, 6, 30):
        cx2, cy2 = tx + ddx, ty + 26
        ic.fill(ic.poly_mask(ic.jitter(cx2, cy2, 22, 30, 10, 0.2)), "#b0602c", "#5a2a14", radial=(cx2 - 10, cy2 - 16, 40),
                noise=0.3)
    back = [200, 225, 250, 290, 315, 340]
    front = [150, 175, 10, 30, 125, 60]
    for dg in back:
        frond(ic, (tx, ty), dg + R.uniform(-8, 8), crown * R.uniform(0.8, 1.0), droop=0.5,
              colors=("#6e7e3e", "#23320f"))
    for dg in front:
        frond(ic, (tx, ty), dg + R.uniform(-8, 8), crown * R.uniform(0.85, 1.05), droop=0.6)
    ic.fill(ic.mask("ellipse", (tx - 16, ty - 12, tx + 16, ty + 12)), "#6a5a3a", "#3a2e1c", noise=0.2)


def cn_roof(ic: Icon, x0: float, x1: float, eave: float, ridge: float, overhang: float = 40, lift: float = 36,
            inset: float = 60, c1="#77787a", c2="#3c3d42", ridge_curl: float = 30) -> Image.Image:
    """Chinese hip roof seen from the front: eave sweeping up at the corners, tile channels running
    down the slope, round tile ends along the eave, heavy ridge with upturned ends. Returns the mask."""
    ts = np.linspace(0, 1, 48)
    ex0, ex1 = x0 - overhang, x1 + overhang
    eave_pts = [(ex0 + (ex1 - ex0) * t, eave - lift * abs(2 * t - 1) ** 3.2) for t in ts]
    rx0, rx1 = x0 + inset, x1 - inset
    top_pts = [(rx1, ridge), (rx0, ridge)]
    pts = eave_pts + top_pts
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (ridge, eave), noise=0.16, chroma=0.06)
    R = ic.random
    lay, d = layer()
    n = int((ex1 - ex0) / 22)
    for i in range(n + 1):
        t = i / n
        xb = ex0 + (ex1 - ex0) * t
        yb = eave - lift * abs(2 * t - 1) ** 3.2
        xt = rx0 + (rx1 - rx0) * t
        tone = R.uniform(-1, 1)
        d.line([(xt, ridge), (xb, yb)], fill=(20, 20, 24, 150), width=5)
        d.line([(xt + 8, ridge), (xb + 9, yb)], fill=(230, 230, 225, 45 + int(25 * tone)), width=4)
    composite(ic, lay, m)
    # soft tonal patches (lichen, repairs)
    for _ in range(6):
        bx, by = R.uniform(ex0, ex1), R.uniform(ridge, eave)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(bx, by, R.uniform(30, 60), R.uniform(12, 24), 8, 0.3))),
                 (90, 100, 70) if R.random() < 0.5 else (0, 0, 0), R.uniform(0.1, 0.2), blur=8)
    # eave: tile ends
    lower = eave_pts + [(x, y - 16) for x, y in eave_pts[::-1]]
    ic.fill(ic.poly_mask(lower), "#4a4a50", "#2a2a2e", noise=0.1)
    for i in range(n + 1):
        t = i / n
        xb = ex0 + (ex1 - ex0) * t
        yb = eave - lift * abs(2 * t - 1) ** 3.2 - 8
        ic.draw.ellipse((xb - 6, yb - 6, xb + 6, yb + 6), fill=(118, 118, 116, 255))
    ic.outline(pts, 5)
    # ridge with upturned ends
    ic.poly([(rx0 - 10, ridge + 8), (rx1 + 10, ridge + 8), (rx1 + 14, ridge - 18), (rx0 - 14, ridge - 18)], "#56575c",
            "#2e2f33", edge=4)
    for sx, sgn in ((rx0 - 12, -1), (rx1 + 12, 1)):
        curl = [(sx, ridge + 6), (sx, ridge - 18), (sx + sgn * 18, ridge - 18 - ridge_curl),
                (sx + sgn * 30, ridge - 12 - ridge_curl), (sx + sgn * 12, ridge - 10), (sx + sgn * 4, ridge + 6)]
        ic.poly(curl, "#5a5b60", "#2e2f33", edge=4)
    ic.line([(rx0 - 6, ridge - 12), (rx1 + 6, ridge - 12)], 3, (220, 220, 215, 90))
    return m


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


SEED = 11
REFS = ("bridge_infrastructure", "pound_lock_canal_infrastructure", "zhixian", "confucian_school")

BAND_TOP, BAND_BOT = 580, 740
WL = 628                         # water line along the footings and the bridge
GRANITE, GRANITE_DK = "#b0a48e", "#6a6054"
WASH, WASH_DK = "#e8dcc2", "#b0a48a"
TILE, TILE_DK = "#55565c", "#26272b"
BR0, BR1 = 96, 566              # bridge extent
ACX, ACR = 331, 186              # arch centre x and radius (springing at the water line)


def cap(ic: Icon, x0: float, x1: float, y: float, h: float = 18, curl: float = 10) -> None:
    """Thin dark tile cap on a wall step, its ends flicked up like a horse head."""
    pts = [(x0 - 12, y + 6), (x1 + 12, y + 6), (x1 + 18, y - h - curl), (x1 + 6, y - h + 2), (x0 - 6, y - h + 2),
           (x0 - 18, y - h - curl)]
    ic.poly(pts, "#6a6b70", TILE_DK, edge=4)
    lay, d = layer()
    for x in np.arange(x0 - 4, x1 + 6, 12):
        d.line([(x, y - h + 4), (x, y + 4)], fill=(20, 20, 24, 120), width=3)
    composite(ic, lay, ic.poly_mask(pts))
    ic.line([(x0 - 6, y - h + 4), (x1 + 6, y - h + 4)], 3, (220, 220, 214, 110))
    ic.shade(ic.mask("rectangle", (x0, y + 6, x1, y + 20)), alpha=0.35, blur=5)


def lattice_window(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    ic.rect((x0 - 8, y0 - 8, x1 + 8, y1 + 8), "#6a4a30", "#44301e", edge=4)
    ic.rect((x0, y0, x1, y1), "#2c2826", "#18140f", noise=0.06, edge=0)
    for x in np.linspace(x0, x1, 4)[1:-1]:
        ic.line([(x, y0), (x, y1)], 4, (110, 80, 52))
    for y in np.linspace(y0, y1, 4)[1:-1]:
        ic.line([(x0, y), (x1, y)], 4, (110, 80, 52))
    ic.shade(ic.mask("rectangle", (x0 - 8, y1 + 8, x1 + 8, y1 + 22)), alpha=0.25, blur=5)


def house_gable(ic: Icon, x0: float, x1: float, eave: float, peak: float, foot: float) -> None:
    """Canal house showing its whitewashed gable end, stepped up in three pairs of horse-head caps."""
    w = x1 - x0
    steps = [(0.0, 0.18, eave), (0.18, 0.36, (eave + peak) / 2 + 10), (0.36, 0.64, peak), (0.64, 0.82, (eave + peak) / 2 + 10),
             (0.82, 1.0, eave)]
    pts = [(x0, foot)]
    for a, b, y in steps:
        pts += [(x0 + w * a, y), (x0 + w * b, y)]
    pts += [(x1, foot)]
    m = ic.poly_mask(pts)
    plaster(ic, m, WASH, WASH_DK, span=(peak, foot))
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0 + w * 0.55, 0, x1, SIZE))), alpha=0.12, blur=20)
    ic.outline(pts, 5)
    for a, b, y in steps:
        cap(ic, x0 + w * a, x0 + w * b, y)
    lattice_window(ic, x0 + w * 0.38, eave + 20, x0 + w * 0.62, eave + 86)
    lattice_window(ic, x0 + w * 0.16, foot - 196, x0 + w * 0.34, foot - 130)
    # door with a small tiled hood and water steps
    dx0, dx1 = x0 + w * 0.56, x0 + w * 0.8
    ic.door(dx0, foot - 150, dx1, foot, arched=False, surround="#b8b2a4")
    cap(ic, dx0 - 10, dx1 + 10, foot - 160, h=22, curl=8)


def house_long(ic: Icon, x0: float, x1: float, eave: float, ridge: float, foot: float) -> None:
    """Taller house with its long side to the canal: tile roof between two firewalls."""
    m = ic.mask("rectangle", (x0, eave - 10, x1, foot))
    plaster(ic, m, WASH, WASH_DK, span=(eave, foot))
    ic.outline([(x0, eave - 10), (x1, eave - 10), (x1, foot), (x0, foot)], 5)
    ic.tiles([(x0 - 10, eave + 6), (x1 + 10, eave + 6), (x1 - 4, ridge), (x0 + 4, ridge)], TILE, TILE_DK, course=24, stagger=22)
    ic.shade(ic.mask("rectangle", (x0, eave + 6, x1, eave + 40)), alpha=0.45, blur=8)
    # firewall at the far end, higher than the ridge
    fw = [(x1 - 34, foot), (x1 - 34, ridge - 60), (x1 + 6, ridge - 60), (x1 + 6, foot)]
    plaster(ic, ic.poly_mask(fw), WASH, WASH_DK, span=(ridge - 60, foot))
    ic.outline(fw, 5)
    cap(ic, x1 - 34, x1 + 6, ridge - 60, h=24, curl=16)
    # upper floor: projecting timber gallery with lattice panels
    gy = eave + 96
    ic.rect((x0 + 10, gy, x1 - 44, gy + 70), "#7a5636", "#4a321e", edge=4)
    for x in np.arange(x0 + 20, x1 - 50, 30):
        ic.line([(x, gy + 6), (x, gy + 64)], 4, (40, 26, 16, 200))
    ic.line([(x0 + 10, gy + 34), (x1 - 44, gy + 34)], 4, (40, 26, 16, 200))
    ic.shade(ic.mask("rectangle", (x0 + 10, gy + 70, x1 - 44, gy + 92)), alpha=0.4, blur=6)
    lattice_window(ic, x0 + 40, foot - 150, x0 + 110, foot - 80)


def footing(ic: Icon, x0: float, x1: float, top: float) -> None:
    ashlar(ic, (x0, top, x1, WL + 40), GRANITE, GRANITE_DK, course=(24, 32), width=(50, 110))
    ic.outline([(x0, top), (x1, top), (x1, WL + 40), (x0, WL + 40)], 5)
    ic.shade(ic.mask("rectangle", (x0, top, x1, top + 12)), (255, 250, 235), 0.15)


def willow(ic: Icon, x: float, base: float) -> None:
    """Weeping willow: leaning trunk, a dark inner curtain, then many long tapering withy strands
    of different lengths over it, the massed crown on top."""
    R = ic.random
    cx, top = x + 10, 150
    # dark inner curtain behind the strands
    hem = [(cx - 150 + 300 * k / 12, 360 + 90 * math.sin(math.pi * k / 12) + R.uniform(-16, 16)) for k in range(13)]
    back = [(cx - 150, 220), (cx + 150, 220)] + hem[::-1]
    ic.fill(ic.poly_mask(back), "#4e5e2a", "#1e2a0e", (220, 460), noise=0.3)
    timber(ic, (x + 10, base), (x - 6, 240), 40, "#6e5a44", "#3a2e22")
    timber(ic, (x - 4, 320), (x + 70, 230), 18, "#6e5a44", "#3a2e22")
    strands = []
    for _ in range(30):
        t = R.random()
        sx = cx - 160 + 320 * t
        sy = top + 70 + 40 * math.sin(math.pi * t) + R.uniform(-10, 20)
        ln = (110 + 190 * math.sin(math.pi * t) ** 0.7) * R.uniform(0.7, 1.05)
        strands.append((R.random(), sx, sy, ln))
    for depth, sx, sy, ln in sorted(strands):
        w = R.uniform(16, 26)
        sway = R.uniform(-18, 18)
        ts = np.linspace(0, 1, 12)
        left = [(sx - w / 2 * (1 - 0.8 * t) + sway * t * t, sy + ln * t) for t in ts]
        right = [(sx + w / 2 * (1 - 0.8 * t) + sway * t * t, sy + ln * t) for t in ts]
        pts = left + right[::-1]
        f = 0.75 + 0.35 * depth
        ic.fill(ic.poly_mask(pts), tuple(int(v * f) for v in (168, 180, 100)), tuple(int(v * f) for v in (56, 72, 30)),
                (sy, sy + ln), noise=0.3)
        ic.line([(sx - w * 0.2 + sway * t * t, sy + ln * t) for t in ts[:-2]], 3, (230, 236, 170, 70))
        ic.outline(pts, 3, (30, 40, 14, 110))
    canopy(ic, cx, top + 50, 150, 70, light="#a8b064", dark="#445424", n=18)


def deck_y(x: float) -> float:
    t = (x - BR0) / (BR1 - BR0)
    return WL - 34 - 226 * math.sin(math.pi * min(max(t, 0), 1)) ** 0.55


def bridge(ic: Icon) -> None:
    xs = np.linspace(BR0, BR1, 60)
    top = [(x, deck_y(x)) for x in xs]
    body = top + [(BR1 + 30, WL + 40), (BR0 - 30, WL + 40)]
    opening = ic.mask("pieslice", (ACX - ACR, WL - ACR, ACX + ACR, WL + ACR), start=180, end=360)
    bm = minus(ic.poly_mask(body), opening)
    ashlar(ic, (BR0 - 30, deck_y(ACX) - 10, BR1 + 30, WL + 40), GRANITE, GRANITE_DK, course=(26, 34), width=(44, 90),
           clip=bm)
    ic.outline(body, 5)
    # through the arch: far canal water, soffit in shadow
    ic.fill(opening, "#6ea6b6", "#2e5e6e", (WL - ACR, WL), noise=0.08)
    ic.shade(ic.intersect(opening, ic.mask("rectangle", (0, 0, SIZE, WL - ACR * 0.45))), (10, 14, 16), 0.75, blur=10)
    ic.shade(ic.intersect(opening, ic.mask("rectangle", (ACX + ACR * 0.3, 0, SIZE, SIZE))), (10, 14, 16), 0.3, blur=12)
    # voussoir ring
    ring = minus(ic.mask("pieslice", (ACX - ACR - 30, WL - ACR - 30, ACX + ACR + 30, WL + ACR + 30), start=180, end=360),
                 opening)
    ic.fill(ring, "#c4bcaa", "#7e776c", (ACX - ACR, ACX + ACR), vertical=False, noise=0.18)
    for a in range(180, 361, 15):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        ic.line([(ACX + ACR * ca, WL + ACR * sa), (ACX + (ACR + 30) * ca, WL + (ACR + 30) * sa)], 3, (60, 54, 46, 190))
    ic.overlay(lambda d: d.arc((ACX - ACR, WL - ACR, ACX + ACR, WL + ACR), 180, 360, fill=(40, 34, 28, 220), width=5))
    # parapet with coping stones and posts, following the hump
    par = [(x, y - 30) for x, y in top]
    pm = ic.poly_mask(par + top[::-1])
    ic.fill(pm, "#b8b2a4", "#7a746a", (deck_y(ACX) - 30, WL), noise=0.18)
    ic.line(par, 10, (206, 200, 186))
    ic.line([(x, y + 3) for x, y in par], 4, (60, 54, 46, 160))
    for x in np.linspace(BR0 + 20, BR1 - 20, 16):  # joints between parapet slabs
        y = deck_y(x)
        ic.line([(x, y - 28), (x, y - 2)], 3, (60, 54, 46, 150))
    ic.shade(ic.poly_mask(top + [(x, y + 26) for x, y in top[::-1]]), alpha=0.35, blur=6)
    # weeds from the joints
    for wx in (BR0 + 20, ACX + 110, BR1 - 10):
        weeds(ic, wx, deck_y(wx) + 40, 36)


def boat(ic: Icon, x0: float, x1: float, wl: float) -> Image.Image:
    """Wupeng boat: narrow hull, black arched bamboo awning."""
    ts = np.linspace(0, 1, 24)
    L = x1 - x0
    gun = [(x0 + L * t, wl - 26 + 6 * math.sin(math.pi * t) - 22 * (1 - t) ** 6 - 16 * t ** 6) for t in ts]
    hull = gun + [(x1 - 20, wl + 12), (x0 + 24, wl + 12)]
    ax0, ax1 = x0 + L * 0.3, x0 + L * 0.72
    aw = [(ax0, wl - 22)] + [(ax0 + (ax1 - ax0) * t, wl - 22 - 56 * math.sin(math.pi * t) ** 0.7) for t in ts] + [(ax1, wl - 22)]
    ic.fill(ic.poly_mask(aw), "#4a4640", "#1c1a18", (wl - 80, wl - 20), noise=0.2)
    for k in range(1, 7):
        xx = ax0 + (ax1 - ax0) * k / 7
        ic.line([(xx, wl - 24), (xx, wl - 22 - 54 * math.sin(math.pi * k / 7) ** 0.7)], 3, (120, 110, 96, 120))
    ic.outline(aw, 4)
    hm = planks(ic, hull, "#7a5a3a", "#3e2c1c", board=12, vertical_boards=False)
    ic.line(gun, 8, (58, 40, 26))
    ic.outline(hull, 4, (40, 26, 16, 190))
    return hm


def draw(ic: Icon) -> None:
    b = band(ic, BAND_TOP, BAND_BOT, x0=16, x1=1008, inset=26, sag=24)
    canopy(ic, 330, 330, 110, 70, light="#96a452", dark="#34441c", n=14)
    house_long(ic, 30, 250, 330, 250, 600)
    footing(ic, 20, 260, 584)
    house_long(ic, 764, 990, 290, 196, 596)
    house_gable(ic, 566, 790, 330, 190, 596)
    footing(ic, 552, 1000, 580)
    for k in range(4):  # water steps down from the gable house door
        y = 580 + k * 14
        ic.rect((730 - k * 8, y, 790 + k * 8, y + 14), "#bcb6a8", "#7e786c", edge=3)
    bridge(ic)
    walls = ic.mask("rectangle", (0, 500, SIZE, SIZE))
    ic.waterline(walls, WL)
    # reflection of the arch closes it into a ring
    ref = minus(ic.mask("ellipse", (ACX - ACR - 30, WL - ACR - 30, ACX + ACR + 30, WL + ACR + 30)),
                ic.mask("ellipse", (ACX - ACR, WL - ACR, ACX + ACR, WL + ACR)))
    ref = ic.intersect(ref, ic.mask("rectangle", (0, WL, SIZE, SIZE)), b)
    ic.shade(ref, (214, 214, 200), 0.22, blur=3)
    inner = ic.intersect(ic.mask("ellipse", (ACX - ACR, WL - ACR, ACX + ACR, WL + ACR)),
                         ic.mask("rectangle", (0, WL + ACR * 0.4, SIZE, SIZE)), b)
    ic.shade(inner, (10, 20, 26), 0.45, blur=12)
    ic.shade(ic.intersect(ic.mask("rectangle", (BR0 - 30, WL, BR1 + 30, WL + 60)), b), (20, 40, 50), 0.25, blur=12)
    for lx in (824, 918):  # red lanterns under the gallery
        ic.line([(lx, 300), (lx, 322)], 3, (40, 30, 20))
        ic.fill(ic.mask("ellipse", (lx - 20, 318, lx + 20, 370)), "#d0503a", "#6a1c14", radial=(lx - 8, 330, 44), noise=0.15)
        ic.overlay(lambda d, lx=lx: d.ellipse((lx - 20, 318, lx + 20, 370), outline=(40, 16, 10, 220), width=4))
        ic.rect((lx - 10, 366, lx + 10, 376), "#3a2a1c", "#1a120c", edge=0)
        ic.line([(lx, 376), (lx, 392)], 4, (200, 150, 60))
    ic.grade["mute"] = 0.96
    ic.shade(ic.intersect(ic.mask("rectangle", (552, WL, 1000, WL + 50)), b), (40, 44, 40), 0.25, blur=12)
    ic.foam(BR0 - 20, 990, WL - 4)
    hm = boat(ic, 600, 860, 690)
    ic.waterline(hm, 692)
    ic.line([(610, 668), (640, 600)], 5, (70, 52, 34))  # mooring line to the steps
    rim_darken(ic)
