"""Nile Canal and Basin Works (nile_navigation_works): a flood basin behind its dykes, fed by a shaduf.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the shaduf. On the mud-brick canal bank two plastered pillars carry the sweep: its clay
counterweight rides high at the back, its bucket hangs down to the canal in front. Behind the bank a
basin of flood water sits between low earthen dykes with young grain on its rim, and a date palm
stands over it. Sand and mud-brick tones set it apart from the green and stone waterways.
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


def mudbrick(ic: Icon, m: Image.Image, box) -> None:
    """Irregular sun-dried mud-brick coursing: uneven course heights and brick lengths, lost bricks,
    patches of plaster render and a few cracks."""
    x0, y0, x1, y1 = box
    ic.fill(m, "#94704c", "#553a24", (y0, y1), noise=0.26, chroma=0.1)
    R = ic.random
    lay, d = layer()
    y = y0
    while y < y1:
        ch = R.uniform(17, 27)
        x = x0 - R.uniform(0, 40)
        while x < x1:
            w = R.uniform(34, 68)
            t = R.uniform(-1, 1)
            col = (255, 222, 180, int(t * 36)) if t > 0 else (30, 16, 8, int(-t * 70))
            if R.random() < 0.05:
                col = (26, 14, 8, 160)
            q = [(x + 2 + R.uniform(-1, 1), y + 2), (x + w - 2, y + 2 + R.uniform(-2, 2)),
                 (x + w - 2 + R.uniform(-2, 2), y + ch - 2), (x + 2, y + ch - 2 + R.uniform(-2, 2))]
            d.polygon(q, fill=col)
            d.line([q[0], q[1]], fill=(255, 232, 196, 50), width=2)
            d.line([q[1], q[2]], fill=(40, 24, 12, 110), width=3)
            x += w
        d.line([(x0, y + ch), (x1, y + ch + R.uniform(-3, 3))], fill=(40, 24, 12, 90), width=3)
        y += ch
    for _ in range(int((x1 - x0) / 120)):
        cx, cy = R.uniform(x0, x1), R.uniform(y0 + 10, y1 - 10)
        pts = [(cx + R.uniform(-4, 4), cy)]
        for _ in range(4):
            pts.append((pts[-1][0] + R.uniform(-10, 10), pts[-1][1] + R.uniform(8, 16)))
        d.line(pts, fill=(30, 18, 10, 150), width=2)
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 170)):
        bx, by = R.uniform(x0, x1), R.uniform(y0 + 14, y1 - 30)
        pts = ic.jitter(bx, by, R.uniform(36, 80), R.uniform(14, 26), 10, 0.3)
        pm = ic.intersect(m, ic.poly_mask(pts))
        ic.fill(pm, "#c8aa80", "#8e7250", (by - 26, by + 26), noise=0.25)
        ic.shade(ic.intersect(pm, ic.mask("rectangle", (0, by + 8, SIZE, SIZE))), (40, 26, 12), 0.25, blur=5)
        ic.overlay(lambda dd, p=pts: dd.line(p + [p[0]], fill=(60, 40, 22, 110), width=2), m)


def jar(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Large porous clay water jar (zir): wide shoulder, tapering foot, short neck and rolled rim."""
    ic.shade(ic.mask("ellipse", (cx - w * 0.55, base - 8, cx + w * 0.75, base + 8)), alpha=0.45, blur=5)
    ts = np.linspace(0, 1, 20)
    right = [(cx + w * 0.5 * math.sin(math.pi * (0.18 + 0.72 * t)) ** 0.7 + w * 0.06 * (1 - t), base - h * 0.84 + h * 0.84 * t)
             for t in ts]
    right[-1] = (cx + w * 0.16, base)
    left = [(2 * cx - x, y) for x, y in right]
    poly = right + left[::-1]
    bm = ic.poly_mask(poly)
    ic.fill(bm, "#c88a56", "#5a2e16", radial=(cx - w * 0.25, base - h * 0.7, h * 1.0), noise=0.22, chroma=0.1)
    ic.shade(ic.intersect(bm, ic.mask("ellipse", (cx - w * 0.3, base - h * 0.82, cx - w * 0.05, base - h * 0.55))),
             (255, 236, 200), 0.28, blur=6)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, base - h * 0.52, SIZE, base - h * 0.44))), (255, 240, 210), 0.12,
             blur=3)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, base - h * 0.3, SIZE, SIZE))), (40, 30, 20), 0.25, blur=8)
    ic.outline(poly, 3, (36, 20, 10, 200))
    nk = [(cx - w * 0.2, base - h * 0.8), (cx - w * 0.16, base - h * 0.95), (cx + w * 0.16, base - h * 0.95),
          (cx + w * 0.2, base - h * 0.8)]
    ic.poly(nk, "#b87a4a", "#6a3a1e", vertical=False, edge=3)
    ic.fill(ic.mask("ellipse", (cx - w * 0.24, base - h - 6, cx + w * 0.24, base - h + 8)), "#d09a68", "#8a5230", noise=0.15)
    ic.fill(ic.mask("ellipse", (cx - w * 0.15, base - h - 2, cx + w * 0.15, base - h + 5)), "#3a2616", "#1c120a", noise=0.1)
    ic.overlay(lambda d: d.ellipse((cx - w * 0.24, base - h - 6, cx + w * 0.24, base - h + 8), outline=(36, 20, 10, 200),
                                   width=3))


def reed_clump(ic: Icon, cx: float, base: float, spread: float, hmax: float, n: int = 22) -> None:
    """Reed clump: tapered leaning blades of varied height fanning out, back blades darker, dark base."""
    R = ic.random
    blades = []
    for _ in range(n):
        x = cx + R.uniform(-spread, spread)
        f = R.uniform(0.35, 1.0)
        out = (x - cx) / spread
        ang = math.radians(out * 26 + R.uniform(-12, 12))
        blades.append((R.random(), x, f, ang))
    for depth, x, f, ang in sorted(blades):
        L = hmax * f
        bend = R.uniform(0.15, 0.5) * (1 if ang >= 0 else -1)
        pts = []
        for t in np.linspace(0, 1, 10):
            a = ang + bend * t * t
            pts.append((x + math.sin(a) * L * t, base - math.cos(a) * L * t + R.uniform(-0.5, 0.5)))
        left, right = [], []
        for i, (px, py) in enumerate(pts):
            q = pts[min(i + 1, 9)]
            p0 = pts[max(i - 1, 0)]
            vx, vy = q[0] - p0[0], q[1] - p0[1]
            vl = math.hypot(vx, vy) or 1
            hw = 6.5 * (1 - i / 9) + 0.8
            left.append((px + vy / vl * hw, py - vx / vl * hw))
            right.append((px - vy / vl * hw, py + vx / vl * hw))
        k = R.random()
        if R.random() < 0.8:
            c1 = (int(110 + 60 * k), int(130 + 36 * k), int(52 + 20 * k))
        else:
            c1 = (178, 158, 96)
        dim = 0.55 + 0.45 * depth
        c1 = tuple(int(v * dim) for v in c1)
        c2 = tuple(int(v * 0.45) for v in c1)
        poly = left + right[::-1]
        ic.fill(ic.poly_mask(poly), c1, c2, (base - L, base), noise=0.18)
        ic.outline(poly, 2, (24, 30, 10, 170))
    ic.shade(ic.mask("ellipse", (cx - spread * 1.3, base - 40, cx + spread * 1.3, base + 16)), (14, 18, 6), 0.5, blur=10)


def lean_palm(ic: Icon, x: float, base: float, tx: float, ty: float, crown: float, w: float = 40) -> None:
    """Single tall date palm leaning left: ringed trunk, a crown of long drooping fronds, a heavy
    hanging cluster of dates under the crown."""
    ts = np.linspace(0, 1, 34)
    cx, cy = x - (x - tx) * 0.05, base - (base - ty) * 0.6
    path = [((1 - t) ** 2 * x + 2 * (1 - t) * t * cx + t * t * tx, (1 - t) ** 2 * base + 2 * (1 - t) * t * cy + t * t * ty)
            for t in ts]
    left, right = [], []
    for i, (px, py) in enumerate(path):
        q = path[min(i + 1, len(path) - 1)]
        p0 = path[max(i - 1, 0)]
        vx, vy = q[0] - p0[0], q[1] - p0[1]
        vl = math.hypot(vx, vy) or 1
        nx, ny = -vy / vl, vx / vl
        hw = w * (1.0 - 0.4 * ts[i]) / 2
        left.append((px - nx * hw, py - ny * hw))
        right.append((px + nx * hw, py + ny * hw))
    pts = left + right[::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, "#a48a68", "#4e3c28", (x - w, x + w), vertical=False, noise=0.25)
    ic.shade(ic.intersect(m, ic.poly_mask(path + right[::-1])), (20, 12, 6), 0.35)
    for i in range(1, len(path) - 1, 2):
        ic.line([left[i], right[i]], 4, (50, 36, 22, 170))
        ic.line([(left[i][0], left[i][1] - 4), (right[i][0], right[i][1] - 4)], 2, (220, 200, 160, 70))
    ic.outline(pts, 4, (40, 28, 18, 170))
    R = ic.random
    back = [205, 238, 275, 310, 338]
    for dg in back:
        frond(ic, (tx, ty), dg + R.uniform(-6, 6), crown * R.uniform(0.85, 1.05), droop=0.55, colors=("#6e7e3e", "#23320f"))
    front = [150, 174, 198, 14, 40]
    for dg in front:
        frond(ic, (tx, ty), dg + R.uniform(-6, 6), crown * R.uniform(0.9, 1.05), droop=0.6)
    # a heavy date cluster hanging on its stalk below the crown
    ic.line([(tx + 4, ty + 10), (tx + 22, ty + 40)], 6, (150, 110, 50))
    cl = ic.jitter(tx + 26, ty + 64, 30, 40, 14, 0.18)
    ic.fill(ic.poly_mask(cl), "#c8702e", "#5a2610", radial=(tx + 14, ty + 40, 70), noise=0.3)
    lay, d = layer()
    for _ in range(40):
        px, py = tx + 26 + R.uniform(-26, 26), ty + 64 + R.uniform(-34, 36)
        d.ellipse((px - 5, py - 6, px + 5, py + 6), fill=(236, 150, 70, 120) if R.random() < 0.5 else (60, 20, 8, 110))
    composite(ic, lay, ic.poly_mask(cl))
    ic.outline(cl, 3, (40, 20, 10, 180))
    ic.line([(tx - 6, ty + 12), (tx - 26, ty + 48)], 5, (150, 110, 50))
    cl2 = ic.jitter(tx - 30, ty + 50, 20, 26, 12, 0.2)
    ic.fill(ic.poly_mask(cl2), "#b8642a", "#4e200c", radial=(tx - 38, ty + 50, 44), noise=0.3)
    ic.outline(cl2, 3, (40, 20, 10, 180))
    ic.fill(ic.mask("ellipse", (tx - 16, ty - 12, tx + 16, ty + 12)), "#6a5a3a", "#3a2e1c", noise=0.2)


SEED = 17
REFS = ("irrigation_systems", "oma_falaj", "polders", "khmer_baray")

BAND_TOP, BAND_BOT = 556, 716
BANK_TOP, BANK_EDGE, BANK_FOOT = 452, 488, 596
WL = BANK_FOOT - 16            # water line on the bank face
BX0, BX1 = 40, 984
MUD, MUD_DK = "#a8845a", "#5e4228"
SAND, SAND_DK = "#bc9e6e", "#86683f"
PIV = (330, 296)  # shaduf pivot
LANDING = (628, 800, 560)      # landing x0, x1, top
STEPS = ((800, 850, 540), (850, 900, 520), (900, 952, 500))
STAIR_WL = WL + 24


def dyke(ic: Icon, pts) -> None:
    """Low earthen dyke: lit crest, darker front slope, a few tufts."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    earth(ic, m, "#c8aa78", "#7e6240", span=(min(ys), max(ys)))
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, min(ys) + (max(ys) - min(ys)) * 0.45, SIZE, SIZE))), (40, 26, 12), 0.3,
             blur=6)
    ic.outline(pts, 4)


def basin(ic: Icon) -> None:
    """Flood water beyond the back dyke, a band of standing grain between the dykes, the feeder channel
    cutting through it from the trough to the basin."""
    water_poly(ic, [(BX0 + 76, 266), (BX1 - 84, 266), (BX1 - 64, 300), (BX0 + 56, 300)], reflect=10, density=1500)
    dyke(ic, [(BX0 + 56, 294), (BX1 - 64, 294), (BX1 - 50, 318), (BX0 + 42, 318)])
    # standing grain, ripening gold with greener patches
    gb = [(BX0 + 42, 316), (BX1 - 50, 316), (BX1 - 30, 408), (BX0 + 22, 408)]
    gm = ic.poly_mask(gb)
    ic.fill(gm, "#d0ae58", "#8a6a2a", (316, 408), noise=0.3, chroma=0.14)
    R = ic.random
    for _ in range(6):
        bx, by = R.uniform(BX0 + 60, BX1 - 60), R.uniform(330, 396)
        ic.shade(ic.intersect(gm, ic.poly_mask(ic.jitter(bx, by, R.uniform(50, 90), R.uniform(14, 24), 9, 0.3))),
                 (80, 110, 30), R.uniform(0.2, 0.35), blur=8)
    lay, d = layer()
    for row in range(5):
        yb = 326 + row * 20
        for x in np.arange(BX0 + 40 + row * 3, BX1 - 30, 9):
            h = R.uniform(18, 30) * (0.8 + row * 0.08)
            xb = x + R.uniform(-3, 3)
            lean = R.uniform(-3, 4)
            d.line([(xb, yb + R.uniform(-3, 3)), (xb + lean, yb - h)], fill=(96, 74, 30, 170), width=3)
            d.line([(xb + lean, yb - h), (xb + lean * 1.4, yb - h - 10)], fill=(240, 212, 122, 220), width=5)
    composite(ic, lay, gm)
    ic.shade(ic.intersect(gm, ic.mask("rectangle", (0, 380, SIZE, SIZE))), (40, 30, 10), 0.25, blur=10)
    ic.outline(gb, 4)
    # feeder channel from the trough gap back through the grain to the basin
    ch = [(392, 410), (446, 410), (472, 316), (452, 316)]
    water_poly(ic, ch, density=700)
    ic.shade(ic.intersect(ic.poly_mask(ch), ic.poly_mask([(392, 410), (412, 410), (456, 316), (452, 316)])), (20, 30, 20),
             0.4, blur=3)
    ic.outline(ch, 3, (40, 28, 16, 200))
    dyke(ic, [(452, 296), (478, 296), (480, 318), (448, 318)])
    # front dyke: a low earthen bank with a gap where the feeder channel enters
    for x0, x1 in ((BX0, 390), (448, BX1)):
        pts = [(x0 + 14, 404), (x1 - 6, 404), (x1, BANK_TOP + 4), (x0, BANK_TOP + 4)]
        dyke(ic, pts)
        ic.shade(ic.poly_mask([(x0, 432), (x1, 432), (x1, BANK_TOP + 4), (x0, BANK_TOP + 4)]), alpha=0.2, blur=8)
    for gx in (130, 560, 760):
        ic.poly(ic.jitter(gx, 406, 34, 10, 7, 0.3), "#8a9a44", "#4e5c24", edge=0)


def stair(ic: Icon) -> Image.Image:
    """Mud-brick water steps running down along the bank face to a landing at the water."""
    blocks = [LANDING] + list(STEPS)
    sm = blank()
    for xa, xb, top in blocks:
        sm = union(sm, ic.mask("rectangle", (xa, top, xb, STAIR_WL + 20)))
    # the stair shades the wall to its right
    ic.shade(ic.mask("rectangle", (STEPS[-1][1], STEPS[-1][2] + 6, STEPS[-1][1] + 22, STAIR_WL)), (20, 12, 6), 0.4, blur=6)
    for xa, xb, top in blocks:
        front = ic.mask("rectangle", (xa, top + 12, xb, STAIR_WL + 20))
        mudbrick(ic, front, (xa, top + 12, xb, STAIR_WL + 20))
        ic.shade(front, (232, 212, 172), 0.4)
        ic.shade(ic.intersect(front, ic.mask("rectangle", (xa + (xb - xa) * 0.6, 0, xb, SIZE))), (30, 18, 8), 0.18, blur=6)
        ic.fill(ic.mask("rectangle", (xa, top, xb, top + 13)), "#e6d2aa", "#bca078", (xa, xb), vertical=False, noise=0.22)
        ic.shade(ic.mask("rectangle", (xa, top + 12, xb, top + 22)), (20, 12, 6), 0.35, blur=4)
        ic.line([(xa, top + 2), (xb, top + 2)], 3, (255, 244, 220, 120))
    prof = [(LANDING[0], STAIR_WL + 20), (LANDING[0], LANDING[2])]
    for xa, xb, top in blocks[1:]:
        prof += [(xa, prof[-1][1]), (xa, top)]
    prof += [(STEPS[-1][1], STEPS[-1][2]), (STEPS[-1][1], STAIR_WL + 20)]
    ic.line(prof, 4)
    ic.line([(LANDING[1], LANDING[2] + 13), (LANDING[1], STAIR_WL)], 3, (40, 24, 12, 150))
    for xa, xb, top in blocks[1:]:
        ic.line([(xa, top + 13), (xb, top + 13)], 3, (40, 24, 12, 150))
    ic.line([(LANDING[0], LANDING[2] + 13), (LANDING[1], LANDING[2] + 13)], 3, (40, 24, 12, 150))
    return sm


def bank(ic: Icon) -> None:
    top = [(BX0, BANK_TOP), (BX1, BANK_TOP), (BX1 + 10, BANK_EDGE), (BX0 - 10, BANK_EDGE)]
    earth(ic, ic.poly_mask(top), SAND, SAND_DK)
    ic.outline(top, 5)
    ch = [(392, 404), (446, 404), (452, BANK_EDGE - 4), (386, BANK_EDGE - 4)]
    water_poly(ic, ch, density=900)
    ic.outline(ch, 4)
    face = [(BX0 - 10, BANK_EDGE), (BX1 + 10, BANK_EDGE), (BX1 + 10, BANK_FOOT), (BX0 - 10, BANK_FOOT)]
    fm = ic.poly_mask(face)
    mudbrick(ic, fm, (BX0 - 10, BANK_EDGE, BX1 + 10, BANK_FOOT))
    ic.shade(ic.mask("rectangle", (BX0 - 10, BANK_EDGE, BX1 + 10, BANK_EDGE + 22)), alpha=0.35, blur=8)
    # wet dark band at the waterline, a little green slime
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, WL - 40, SIZE, SIZE))), (22, 20, 12), 0.5, blur=8)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, WL - 16, SIZE, SIZE))), (50, 70, 30), 0.25, blur=4)
    ic.outline(face, 5)
    ic.waterline(ic.mask("rectangle", (0, 500, SIZE, SIZE)), WL)
    ic.line([(BX0, WL), (BX1, WL)], 4, (20, 30, 30, 140))
    sm = stair(ic)
    ic.waterline(sm, STAIR_WL)
    ic.line([(LANDING[0], STAIR_WL), (STEPS[-1][1], STAIR_WL)], 4, (20, 30, 30, 150))
    jar(ic, 684, LANDING[2] + 10, 52, 74)
    jar(ic, 742, LANDING[2] + 12, 40, 56)


def shaduf(ic: Icon) -> None:
    px, py = PIV
    top = py + 4
    for x in (px - 54, px + 54):
        R = ic.random
        lft = [(x - 48, BANK_TOP + 22), (x - 45 + R.uniform(-3, 3), BANK_TOP - 60), (x - 40 + R.uniform(-3, 3), top + 80),
               (x - 33, top + 10)]
        rgt = [(x + 33, top + 10), (x + 38 + R.uniform(-3, 3), top + 90), (x + 44 + R.uniform(-3, 3), BANK_TOP - 50),
               (x + 48, BANK_TOP + 22)]
        cap = [(x - 33, top + 10), (x - 26, top - 2), (x - 12, top + 4), (x, top - 4), (x + 14, top + 3), (x + 26, top - 3),
               (x + 33, top + 10)]
        pts = chaikin_open(lft) + cap[1:-1] + chaikin_open(rgt)
        pm = ic.poly_mask(pts)
        ic.fill(pm, "#d6bc92", "#7a5e3e", (x - 40, x + 44), vertical=False, noise=0.3, chroma=0.1)
        ic.shade(ic.intersect(pm, ic.mask("rectangle", (x + 10, 0, SIZE, SIZE))), (30, 18, 8), 0.3, blur=8)
        ic.shade(ic.intersect(pm, ic.mask("rectangle", (0, BANK_TOP - 50, SIZE, SIZE))), (50, 36, 20), 0.3, blur=12)
        for _ in range(5):
            bx, by = x + R.uniform(-30, 30), R.uniform(top + 20, BANK_TOP)
            ic.shade(ic.intersect(pm, ic.poly_mask(ic.jitter(bx, by, R.uniform(8, 18), R.uniform(6, 14), 7, 0.3))),
                     (60, 40, 20) if R.random() < 0.6 else (255, 240, 210), R.uniform(0.12, 0.22), blur=3)
        cx = x + R.uniform(-10, 10)
        ic.line([(cx, top + 40), (cx + 4, top + 70), (cx - 2, top + 96)], 2, (40, 24, 12, 150))
        ic.outline(pts, 4)
        ic.shade(ic.mask("ellipse", (x - 60, BANK_TOP + 8, x + 70, BANK_TOP + 36)), alpha=0.35, blur=8)
    timber(ic, (px - 92, py + 6), (px + 92, py + 6), 22, "#7a5a3a", "#44301c")
    # packed mud around the crossbar ends on the pillar heads
    for x in (px - 54, px + 54):
        lump = ic.jitter(x, py + 4, 30, 16, 10, 0.25)
        ic.fill(ic.poly_mask(lump), "#ceb48a", "#80643f", radial=(x - 14, py - 6, 44), noise=0.3)
        ic.outline(lump, 3, (40, 26, 14, 190))
    # trough at the pillar foot where the bucket is emptied
    ic.poly([(362, BANK_TOP + 2), (476, BANK_TOP + 2), (470, BANK_TOP + 30), (368, BANK_TOP + 30)], "#a4845c", "#5e4428", edge=4)
    ic.fill(ic.mask("rectangle", (370, BANK_TOP + 6, 468, BANK_TOP + 14)), "#8cc0cc", "#4a8494", noise=0.05)
    # the sweep: counterweight high at the back-left, bucket end out over the canal
    cw = (120, 176)
    end = (596, 428)
    ic.shade(ic.poly_mask([(cw[0] + 30, cw[1] + 60), (end[0] + 20, end[1] + 40), (end[0] + 30, end[1] + 60),
                           (cw[0] + 40, cw[1] + 80)]), alpha=0.18, blur=14)
    timber(ic, cw, end, 28, "#94704a", "#50381f")
    ic.overlay(lambda d: d.line([(px - 12, py - 10), (px + 12, py + 22)], fill=(40, 30, 20, 255), width=12))
    body = ic.jitter(cw[0] + 8, cw[1] + 34, 66, 56, 16, 0.07)
    ic.fill(ic.poly_mask(body), "#9a7652", "#3e2c1a", radial=(cw[0] - 30, cw[1] - 4, 130), noise=0.3)
    ic.outline(body, 4, (40, 28, 16, 190))
    ic.line([(cw[0] - 30, cw[1] + 2), (cw[0] + 40, cw[1] + 62)], 6, (60, 44, 28, 200))
    ic.line([(cw[0] + 44, cw[1] + 2), (cw[0] - 24, cw[1] + 64)], 6, (60, 44, 28, 200))
    # the bucket dips into the canal just off the landing
    bx, by = end[0] + 6, WL + 58
    ic.line([end, (bx, by - 100)], 8, (70, 52, 34))
    bucket = [(bx - 46, by - 62), (bx + 46, by - 62), (bx + 36, by + 8), (bx - 36, by + 8)]
    ic.poly(bucket, "#9a7450", "#40281a", (bx - 46, bx + 46), vertical=False, edge=5)
    ic.line([(bx - 43, by - 38), (bx + 42, by - 38)], 6, (60, 40, 24))
    ic.fill(ic.mask("ellipse", (bx - 46, by - 74, bx + 46, by - 50)), "#7ab0bc", "#3a6a78", noise=0.1)
    ic.overlay(lambda d: d.ellipse((bx - 46, by - 74, bx + 46, by - 50), outline=(40, 28, 16, 220), width=5))
    ic.line([(bx - 43, by - 62), (bx, by - 100), (bx + 43, by - 62)], 6, (60, 44, 28))
    wly = by - 22
    bm = ic.poly_mask(bucket)
    ic.waterline(bm.filter(ImageFilter.MaxFilter(9)), wly)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, wly + 4, SIZE, SIZE))), (60, 40, 20), 0.3, blur=4)
    lay, d = layer()
    for rx, ry, a, wdt in ((62, 12, 230, 6), (92, 18, 170, 5), (124, 24, 110, 4)):
        for s0, s1 in ((196, 250), (262, 330), (345, 400), (20, 90), (110, 170)):
            d.arc((bx - rx, wly - ry, bx + rx, wly + ry), s0 + ic.random.uniform(-6, 6), s1 + ic.random.uniform(-6, 6),
                  fill=(232, 244, 245, a), width=wdt)
    ic.image.alpha_composite(lay)


def chaikin_open(pts, n: int = 2) -> list:
    for _ in range(n):
        out = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            out += [(0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by), (0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by)]
        pts = out + [pts[-1]]
    return pts


def draw(ic: Icon) -> None:
    b = band(ic, BAND_TOP, BAND_BOT, x0=18, x1=1006, inset=24, sag=26)
    basin(ic)
    lean_palm(ic, 906, BANK_TOP + 16, 816, 118, 172, w=42)
    bank(ic)
    shaduf(ic)
    lay, d = layer()
    R = ic.random
    for _ in range(26):
        x, y = R.uniform(40, 980), R.uniform(WL + 50, BAND_BOT + 10)
        if abs(x - 602) < 150 and y < WL + 80:
            continue
        L = R.uniform(16, 44)
        d.arc((x, y - 8, x + L, y + 8), R.uniform(195, 215), R.uniform(320, 345), fill=(226, 242, 245, R.randint(100, 190)),
              width=R.choice((3, 4, 5)))
        if R.random() < 0.5:
            d.line([(x + 6, y + 7), (x + L, y + 8)], fill=(18, 44, 58, 80), width=3)
    composite(ic, lay, b)
    reed_clump(ic, 120, WL + 30, 70, 170, 26)
    reed_clump(ic, 230, WL + 34, 40, 110, 14)
    reed_clump(ic, 972, WL + 30, 30, 120, 12)
    ic.grade["gamma"] = 0.76
    rim_darken(ic)
