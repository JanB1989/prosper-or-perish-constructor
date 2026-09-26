"""Lowland Sluice Works (lowland_sluice_works): a Dutch outlet sluice in a grassed dyke.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the red-brick sluice head set into the green dyke, two arched culverts pouring polder
water into the outer channel, and above them the timber frame with two raised lift gates and their
windlass wheels. Brick wing walls splay into the dyke slopes; reeds at the dyke foot. Unlike the
vanilla pound lock (grey stone, mitre gates head-on) the gates here are vertical lift doors raised
above a brick facade, and the dyke carries the picture.
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
    ts = np.linspace(0, 1, 18)
    spine = [(bx + dx * L * t, by + dy * L * t + droop * L * t * t) for t in ts]
    m = blank()
    dm = ImageDraw.Draw(m)
    for i, t in enumerate(ts[1:], 1):
        px, py = spine[i]
        qx, qy = spine[i - 1]
        tx, ty = px - qx, py - qy
        tl = math.hypot(tx, ty) or 1
        tx, ty = tx / tl, ty / tl
        ln = L * 0.30 * math.sin(math.pi * min(1, t * 1.1)) ** 0.6 + 8
        for s in (1, -1):
            nx, ny = -ty * s, tx * s
            ex, ey = px + (nx * 0.8 + tx * 0.5) * ln, py + (ny * 0.8 + tx * 0.0 + 0.55) * ln
            dm.polygon([(qx, qy), (px + nx * 5, py + ny * 5), (ex, ey), (px, py)], fill=255)
    ic.fill(m, colors[0], colors[1], radial=(bx - L * 0.2, by - L * 0.3, L * 1.3), noise=0.3, chroma=0.14)
    lay, d = layer()
    d.line(spine, fill=(150, 150, 80, 220), width=5, joint="curve")
    composite(ic, lay)
    ic.shade(ic.intersect(m, ic.poly_mask(spine + [(x + 30, y + 60) for x, y in spine[::-1]])), (10, 20, 5), 0.3, blur=6)


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


SEED = 41
REFS = ("pound_lock_canal_infrastructure", "polders", "irrigation_systems", "bridge_infrastructure")

FX0, FX1 = 330, 700           # sluice facade
COPE, FACE, FOOT = 250, 282, 730
CREST, TOE = 344, 668         # dyke crest and toe
BAND_TOP, BAND_BOT = 640, 800
ARCHES = ((372, 492), (538, 658))
SPRING = 484                  # arch springing line
BRICK, BRICK_DK = "#9c5c44", "#5a3426"
QUOIN, QUOIN_DK = "#cbbfa6", "#8e826c"


def dyke(ic: Icon) -> None:
    # pollard willow standing on the crest behind the road
    timber(ic, (206, CREST - 6), (198, 262), 40, "#7a6650", "#3e3226")
    for dx in (-80, -30, 30, 80):
        ic.line([(198, 266), (198 + dx, 190 - abs(dx) * 0.3)], 10, (90, 76, 56))
    canopy(ic, 196, 214, 160, 104, light="#9aa45a", dark="#3c4a22", n=22)
    left = [(26, TOE + 10), (116, CREST + 8), (FX0 + 10, CREST), (FX0 + 10, TOE + 10)]
    right = [(FX1 - 10, CREST), (904, CREST + 6), (998, TOE + 10), (FX1 - 10, TOE + 10)]
    for pts in (left, right):
        m = ic.poly_mask(pts)
        turf(ic, m, span=(CREST, TOE))
        ic.outline(pts, 5)
    # crest road, lit, with a darker verge where the slope turns
    road = [(108, CREST - 16), (FX0 + 10, CREST - 20), (FX0 + 10, CREST + 6), (116, CREST + 10)]
    road_r = [(FX1 - 10, CREST - 20), (912, CREST - 14), (904, CREST + 8), (FX1 - 10, CREST + 6)]
    for pts in (road, road_r):
        earth(ic, ic.poly_mask(pts), "#b49a70", "#8a7050")
        ic.outline(pts, 4)
    ic.shade(ic.poly_mask([(116, CREST + 10), (FX0, CREST + 6), (FX0, CREST + 40), (136, CREST + 44)]), alpha=0.25, blur=10)
    ic.shade(ic.poly_mask([(FX1, CREST + 6), (904, CREST + 8), (920, CREST + 44), (FX1, CREST + 40)]), alpha=0.25, blur=10)
    # a worn footpath running down the slope, a few stones on the toe
    path = [(250, CREST + 8), (282, CREST + 8), (170, TOE + 4), (120, TOE + 4)]
    earth(ic, ic.poly_mask(path), "#a4906a", "#7a6448")
    for sx in (800, 846, 890):
        ic.rock(ic.jitter(sx, TOE - 4, 22, 14, 7, 0.2), "#9a9080", "#5a544c", facets=2)
    # right slope a little darker (turned from the light)
    ic.shade(ic.poly_mask(right), (10, 20, 8), 0.16, blur=20)


def wing(ic: Icon, x_in: float, x_out: float) -> None:
    """Brick wing wall splaying out along the dyke slope, stone coping on its sloped head."""
    top_in, top_out = COPE + 60, TOE - 60
    pts = [(x_in, top_in), (x_out, top_out), (x_out, FOOT), (x_in, FOOT)]
    m = ic.poly_mask(pts)
    lo, hi = min(x_in, x_out), max(x_in, x_out)
    bricks(ic, m, (lo, top_in, hi, FOOT), BRICK, BRICK_DK)
    ic.shade(m, (0, 0, 0), 0.18 if x_out > x_in else 0.05)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, FOOT - 110, SIZE, SIZE))), (22, 30, 20), 0.4, blur=18)
    ic.outline(pts, 5)
    cap = [(x_in, top_in - 22), (x_out, top_out - 22), (x_out, top_out + 4), (x_in, top_in + 4)]
    ic.poly(cap, QUOIN, QUOIN_DK, edge=4)
    ic.shade(ic.poly_mask([(x_in, top_in + 4), (x_out, top_out + 4), (x_out, top_out + 18), (x_in, top_in + 18)]),
             alpha=0.4, blur=5)


def facade(ic: Icon) -> None:
    m = ic.mask("rectangle", (FX0, FACE, FX1, FOOT))
    bricks(ic, m, (FX0, FACE, FX1, FOOT), BRICK, BRICK_DK)
    # stone quoins at both corners and a stone string course at the springing
    for qx in (FX0, FX1 - 44):
        y, k = FACE, 0
        while y < FOOT:
            w = 44 if k % 2 == 0 else 30
            x0 = qx if qx == FX0 else FX1 - w
            ic.fill(ic.mask("rectangle", (x0, y, x0 + w, y + 36)), QUOIN, QUOIN_DK, (x0, x0 + w), vertical=False, noise=0.2)
            ic.overlay(lambda d, b=(x0, y, x0 + w, y + 36): d.rectangle(b, outline=(60, 50, 40, 150), width=3))
            y += 36
            k += 1
    ic.fill(ic.mask("rectangle", (FX0, SPRING - 90, FX1, SPRING - 66)), QUOIN, QUOIN_DK, (FX0, FX1), vertical=False, noise=0.2)
    ic.shade(ic.mask("rectangle", (FX0, SPRING - 66, FX1, SPRING - 54)), alpha=0.35, blur=5)
    # arched culverts: stone voussoirs, dark throat, water pouring out
    for ax0, ax1 in ARCHES:
        cx, r = (ax0 + ax1) / 2, (ax1 - ax0) / 2
        ring = ic.mask("ellipse", (ax0 - 26, SPRING - r - 26, ax1 + 26, SPRING + r + 26))
        ring = union(ring, ic.mask("rectangle", (ax0 - 26, SPRING, ax1 + 26, FOOT)))
        ic.fill(ring, QUOIN, QUOIN_DK, (ax0 - 26, ax1 + 26), vertical=False, noise=0.2)
        for a in range(180, 361, 20):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            ic.line([(cx + r * ca, SPRING + r * sa), (cx + (r + 26) * ca, SPRING + (r + 26) * sa)], 3, (60, 50, 40, 170))
        ic.poly([(cx - 14, SPRING - r - 30), (cx + 14, SPRING - r - 30), (cx + 10, SPRING - r + 4), (cx - 10, SPRING - r + 4)],
                "#d8ccb2", "#9a8e76", edge=3)
        throat = union(ic.mask("ellipse", (ax0, SPRING - r, ax1, SPRING + r)), ic.mask("rectangle", (ax0, SPRING, ax1, FOOT)))
        ic.fill(throat, "#1e1a16", "#100e0c", noise=0.05)
        ic.shade(ic.intersect(throat, ic.mask("rectangle", (ax0, 0, ax0 + 30, SIZE))), (120, 110, 100), 0.15, blur=6)
        # the outflow: a smooth glassy sheet over the sill, breaking white below
        sill = SPRING + 60
        sheet = [(ax0 + 6, sill), (ax1 - 6, sill), (ax1 + 8, FOOT - 20), (ax0 - 8, FOOT - 20)]
        ic.fill(ic.poly_mask(sheet), "#9ccad4", "#3e7486", (sill, FOOT), noise=0.08)
        lay, d = layer()
        for x in np.arange(ax0 + 10, ax1 - 4, 13):
            d.line([(x, sill + 6), (x + (x - cx) * 0.12, FOOT - 24)], fill=(240, 250, 250, ic.random.randint(120, 200)), width=4)
        d.line([(ax0 + 6, sill + 3), (ax1 - 6, sill + 3)], fill=(245, 252, 252, 230), width=6)
        composite(ic, lay, ic.poly_mask(sheet))
    ic.outline([(FX0, FACE), (FX1, FACE), (FX1, FOOT), (FX0, FOOT)], 5)
    # coping
    kerb(ic, FX0 - 16, FX1 + 16, COPE, FACE, lip=18)
    ic.outline([(FX0 - 16, COPE), (FX1 + 16, COPE), (FX1 + 16, FACE), (FX0 - 16, FACE)], 5)
    # right third of the facade in the shade of the gate frame, grime at the foot
    ic.shade(m, (0, 0, 0), 0.0)
    ic.shade(ic.mask("rectangle", (FX1 - 90, FACE, FX1, FOOT)), alpha=0.18, blur=30)


def gates(ic: Icon) -> None:
    """Timber lift-gate frame on the coping: three posts, a head beam, two raised plank gates hung on
    chains from windlass wheels."""
    top = 84
    posts = (352, 515, 678)
    # raised gates between the posts (behind the posts)
    for (a, b), lift in zip(zip(posts, posts[1:]), (104, 104)):
        g0, g1 = a + 16, b - 16
        gm = planks(ic, [(g0, lift), (g1, lift), (g1, COPE + 4), (g0, COPE + 4)], "#8a6444", "#4a3222", board=24)
        for y in (lift + 18, (lift + COPE) / 2 + 4, COPE - 20):
            timber(ic, (g0, y), (g1, y + 3), 14, "#6e4c30", "#3e2a1a")
        ic.shade(ic.intersect(gm, ic.mask("rectangle", (g0, COPE - 50, g1, COPE + 4))), (30, 40, 30), 0.35, blur=10)
        # dripping water from the gate bottom edge
        lay, d = layer()
        for x in np.arange(g0 + 12, g1 - 6, 22):
            d.line([(x, COPE - 6), (x + 1, COPE + ic.random.uniform(4, 14))], fill=(200, 230, 236, 150), width=4)
        composite(ic, lay)
        # chains from the wheels
        cx = (a + b) / 2
        ic.line([(cx - 20, top + 26), (cx - 20, lift + 6)], 5, (46, 44, 44))
        ic.line([(cx + 20, top + 26), (cx + 20, lift + 6)], 5, (46, 44, 44))
    for x in posts:
        timber(ic, (x, top - 10), (x, COPE + 6), 38, "#8e6644", "#4e3522")
    timber(ic, (posts[0] - 30, top), (posts[-1] + 30, top + 4), 38, "#8e6644", "#4e3522")
    timber(ic, (posts[0], top + 60), (posts[0] - 40, COPE + 2), 16, "#7c5838", "#4a321f")
    timber(ic, (posts[-1], top + 60), (posts[-1] + 40, COPE + 2), 16, "#7c5838", "#4a321f")
    for a, b in zip(posts, posts[1:]):
        cx = (a + b) / 2
        wy, R = top - 50, 58
        # wheel pedestal on the head beam
        ic.poly([(cx - 30, top - 14), (cx + 30, top - 14), (cx + 16, wy + 4), (cx - 16, wy + 4)], "#7c5838", "#4a321f", edge=4)
        ic.fill(ic.mask("ellipse", (cx - R, wy - R, cx + R, wy + R)), "#9a7250", "#4a3222",
                radial=(cx - 24, wy - 30, 110), noise=0.18)
        ic.fill(ic.mask("ellipse", (cx - R + 16, wy - R + 16, cx + R - 16, wy + R - 16)), "#2a2018", "#1a140e", noise=0.05)
        for k in range(6):
            ang = math.radians(k * 60 + 15)
            ic.line([(cx, wy), (cx + (R - 8) * math.cos(ang), wy + (R - 8) * math.sin(ang))], 10, (128, 94, 60))
        ic.overlay(lambda d, cx=cx, wy=wy, R=R: d.arc((cx - R + 8, wy - R + 8, cx + R - 8, wy + R - 8), 190, 280,
                                                      fill=(255, 230, 190, 90), width=5))
        ic.overlay(lambda d, cx=cx, wy=wy, R=R: d.ellipse((cx - R, wy - R, cx + R, wy + R), outline=(40, 26, 16, 200), width=5))
        ic.fill(ic.mask("ellipse", (cx - 13, wy - 13, cx + 13, wy + 13)), "#5a5a5a", "#222222", noise=0.05)
    # the frame casts a soft shadow down onto the coping and facade (light from upper left)
    ic.shade(ic.mask("rectangle", (posts[0] + 20, COPE + 20, posts[-1] + 40, COPE + 60)), alpha=0.22, blur=16)


def draw(ic: Icon) -> None:
    b = band(ic, BAND_TOP, BAND_BOT, x0=28, x1=996, inset=24, sag=24)
    dyke(ic)
    wing(ic, FX0, 214)
    wing(ic, FX1, 816)
    facade(ic)
    gates(ic)
    walls = union(ic.mask("rectangle", (200, 400, 830, FOOT + 60)))
    ic.waterline(walls, FOOT - 22)
    ic.foam(214, 816, FOOT - 22)
    for ax0, ax1 in ARCHES:  # white water where the culverts discharge
        splash(ic, ax0 - 20, ax1 + 20, FOOT - 10, b, 22)
        ic.overlay(lambda d, ax0=ax0, ax1=ax1: [d.arc((x, FOOT + 10 + k * 26, x + 60, FOOT + 34 + k * 26), 200, 340,
                                                      fill=(236, 246, 246, 200), width=6)
                                               for k in range(3) for x in np.arange(ax0 - 30 - k * 20, ax1 + k * 20, 70)], b)
    reeds(ic, 60, 200, TOE + 6, 120, clip=None)
    reeds(ic, 836, 972, TOE + 6, 110, clip=None)
    weeds(ic, 250, CREST + 30, 60, hang=False)
    weeds(ic, 780, CREST + 40, 50, hang=False)
    rim_darken(ic)
