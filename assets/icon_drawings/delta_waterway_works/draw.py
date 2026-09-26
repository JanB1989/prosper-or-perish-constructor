"""Delta Waterway Works (delta_waterway_works): a channel forking into two embanked distributaries.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the fork. A dredged channel comes out of the back of the delta land and splits into two
arms that run out into open water at the front. Each arm is lined by raised earthen embankments
with wattle facing and reed beds; paddy fields fill the land between, a sampan poles along the
right arm, and palms and a thatched boat shed stand at the back. Seen from a raised camera like the
vanilla polders, but the land is cut by the forked channel instead of terraced.
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


def surf(ic: Icon, m: Image.Image, x0: float, x1: float, y0: float, y1: float, n: int = 46) -> None:
    """Open water texture: irregular short strokes and broken crests, never in rows."""
    R = ic.random
    lay, d = layer()
    for _ in range(n):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        f = (y - y0) / max(1, y1 - y0)
        L = R.uniform(14, 40) * (0.8 + 0.6 * f)
        w = R.choice((3, 4, 5, 6))
        a = R.randint(110, 220)
        if R.random() < 0.55:
            d.arc((x, y - 8, x + L, y + 8), R.uniform(195, 215), R.uniform(320, 345), fill=(226, 242, 245, a), width=w)
        else:
            d.line([(x, y), (x + L * 0.6, y - R.uniform(0, 3)), (x + L, y + R.uniform(-2, 2))], fill=(226, 242, 245, a),
                   width=w, joint="curve")
        if R.random() < 0.5:
            d.line([(x + 6, y + 7), (x + L * R.uniform(0.6, 1.1), y + 8)], fill=(18, 44, 58, 90), width=3)
    composite(ic, lay, m)


SEED = 29
REFS = ("polders", "irrigation_systems", "terraces", "khmer_baray")

BACK, FRONT, FACE = 262, 600, 646     # land top back edge, front edge, front face foot
BAND_TOP, BAND_BOT = 600, 716
VP = (512, -700)                      # vanishing point of the field bunds


def land_poly():
    return [(170, BACK), (860, BACK), (1000, FRONT), (24, FRONT)]


def stroke(ic: Icon, path, w0: float, w1: float) -> Image.Image:
    """Mask of a thick polyline whose width grows from w0 to w1 (a channel in perspective)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    ends = np.cumsum(seg)
    total = ends[-1]
    m = blank()
    d = ImageDraw.Draw(m)
    for s in np.arange(0, total + 1, 4):
        i = min(int(np.searchsorted(ends, s)), len(seg) - 1)
        t = (s - (ends[i] - seg[i])) / seg[i]
        x, y = pts[i] + (pts[i + 1] - pts[i]) * t
        r = (w0 + (w1 - w0) * s / total) / 2
        d.ellipse((x - r, y - r * 0.55, x + r, y + r * 0.55), fill=255)
    return m


def curve(p0, p1, p2, n: int = 24):
    ts = np.linspace(0, 1, n)
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in ts]


FORK = (492, 404)
MAIN = curve((604, BACK - 30), (540, 330), FORK)
LEFT = curve(FORK, (350, 470), (186, FRONT + 40))
RIGHT = curve(FORK, (630, 466), (826, FRONT + 40))
SHED = (596, 824)


def shed(ic: Icon) -> None:
    """Thatched boat shed on stilts over the head of the channel, at the back right."""
    x0, x1 = SHED
    eave, ridge, floor = 196, 78, 256
    for x in (x0 + 16, x0 + 114, x1 - 16):
        timber(ic, (x, floor - 6), (x, BACK + 26), 16, "#7a5e40", "#3e2e1e")
    planks(ic, [(x0 + 10, eave), (x1 - 10, eave), (x1 - 10, floor), (x0 + 10, floor)], "#a08058", "#5e4830", board=22)
    ic.rect((x0 + 58, eave + 14, x0 + 114, floor - 4), "#2a2420", "#18140f", edge=3)
    ic.rect((x0 + 160, eave + 16, x0 + 200, eave + 44), "#2a2420", "#18140f", edge=3)
    roof = [(x0 - 30, eave + 10), (x1 + 30, eave + 10), (x1 - 20, ridge), (x0 + 20, ridge)]
    ic.fill(ic.poly_mask(roof), "#c0a468", "#6e5a30", (ridge, eave), noise=0.3)
    lay, d = layer()
    for _ in range(260):
        x = ic.random.uniform(x0 - 30, x1 + 30)
        y = ic.random.uniform(ridge, eave)
        t = ic.random.uniform(-1, 1)
        col = (255, 236, 190, int(70 * t)) if t > 0 else (40, 26, 10, int(-80 * t))
        d.line([(x, y), (x + ic.random.uniform(-3, 3), y + ic.random.uniform(16, 34))], fill=col, width=3)
    composite(ic, lay, ic.poly_mask(roof))
    ic.shade(ic.poly_mask([(x0 - 30, eave - 10), (x1 + 30, eave - 10), (x1 + 30, eave + 10), (x0 - 30, eave + 10)]),
             alpha=0.3, blur=6)
    ic.outline(roof, 5)
    ic.shade(ic.mask("rectangle", (x0 + 10, eave + 10, x1 - 10, eave + 34)), alpha=0.4, blur=8)


def fields(ic: Icon, land: Image.Image) -> None:
    """Paddy plots of clearly different states (flooded, young rice, ripening), bunds lit on top."""
    ic.fill(land, "#7a8c40", "#4a5c24", (BACK, FRONT), noise=0.3, chroma=0.16)
    R = ic.random
    fx = np.linspace(-500, 1500, 16) + np.array([R.uniform(-24, 24) for _ in range(16)])
    ys = [BACK]
    while ys[-1] < FRONT:
        ys.append(ys[-1] + 34 + (ys[-1] - BACK) * 0.22 + R.uniform(-6, 6))

    def at(x, y):
        return VP[0] + (x - VP[0]) * (y - VP[1]) / (FRONT + 20 - VP[1])

    kinds = ["flood", "young", "young", "mid", "mid", "mid", "ripe", "flood", "young"]
    for a, bx in zip(fx, fx[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            cell = [(at(a, y0), y0), (at(bx, y0), y0), (at(bx, y1), y1), (at(a, y1), y1)]
            cm = ic.intersect(ic.poly_mask(cell), land)
            if not cm.getbbox():
                continue
            k = R.choice(kinds)
            if k == "flood":
                ic.fill(cm, "#a2b6ba", "#607e88", (y0, y1), noise=0.08, chroma=0.05)
                ic.shade(ic.intersect(cm, ic.poly_mask([cell[0], (cell[0][0] + 40, y0), (cell[3][0] + 70, y1),
                                                         (cell[3][0] + 30, y1)])), (240, 248, 250), 0.22, blur=5)
                lay, d = layer()
                for _ in range(5):
                    x = R.uniform(cell[3][0], cell[2][0])
                    y = R.uniform(y0 + 4, y1 - 4)
                    d.line([(x, y), (x + R.uniform(-2, 2), y - 8)], fill=(96, 140, 60, 200), width=3)
                composite(ic, lay, cm)
            elif k == "young":
                ic.shade(cm, (150, 196, 70), 0.45)
            elif k == "ripe":
                ic.shade(cm, (80, 72, 18), 0.5)
                ic.shade(cm, (190, 160, 60), 0.18)
            else:
                ic.shade(cm, (30, 40, 10), R.uniform(0.05, 0.2))
    lay, d = layer()
    for x in fx:
        d.line([(at(x, FRONT + 20), FRONT + 20), (at(x, BACK - 10), BACK - 10)], fill=(92, 80, 46, 200), width=7)
        d.line([(at(x, FRONT + 20) - 3, FRONT + 20), (at(x, BACK - 10) - 3, BACK - 10)], fill=(226, 214, 160, 110), width=2)
    for y in ys:
        d.line([(0, y), (SIZE, y)], fill=(92, 80, 46, 200), width=6)
        d.line([(0, y - 3), (SIZE, y - 3)], fill=(226, 214, 160, 120), width=2)
    for _ in range(200):
        x, yy = R.uniform(24, 1000), R.uniform(BACK, FRONT)
        h = 6 + 14 * (yy - BACK) / (FRONT - BACK)
        d.line([(x, yy), (x + R.uniform(-3, 3), yy - h)], fill=(170, 196, 90, 120), width=3)
    composite(ic, lay, land)


def draw(ic: Icon) -> None:
    b = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=14, x1=1010, inset=20, sag=24, light=W_LIGHT, deep=W_DEEP,
                      surf=False)
    # deeper water where the two arms run out into the open water
    for mx in (LEFT[-1][0], RIGHT[-1][0]):
        ic.shade(ic.intersect(b, ic.mask("ellipse", (mx - 150, BAND_TOP - 20, mx + 150, BAND_TOP + 90))), (8, 30, 44), 0.45,
                 blur=24)
    surf(ic, b, 20, 1000, BAND_TOP + 30, BAND_BOT + 14)
    # palms at the back left, the boat shed back right (behind the land)
    palm(ic, 150, BACK + 20, 128, 104, 170, w=36)
    palm(ic, 286, BACK + 20, 306, 150, 140, w=30)
    shed(ic)

    lp = land_poly()
    land = ic.poly_mask(lp)
    fields(ic, land)
    face = [(24, FRONT), (1000, FRONT), (996, FACE), (28, FACE)]
    fm = ic.poly_mask(face)
    earth(ic, fm, "#8a6c48", "#4e3a26")
    ic.shade(fm, (20, 30, 20), 0.2)
    ic.outline(face, 5)
    ic.outline(lp, 5)

    ground = union(land, fm)
    chan = union(stroke(ic, MAIN, 72, 104), stroke(ic, LEFT, 104, 180), stroke(ic, RIGHT, 104, 180))
    chan = ic.intersect(chan, ground)
    # embankments with a body: grassy lit crest, dark earth side down to the water, cast shadows
    bank = ic.intersect(minus(chan.filter(ImageFilter.MaxFilter(71)), chan), ground)
    side = ic.intersect(minus(chan.filter(ImageFilter.MaxFilter(35)), chan), bank)
    crest = minus(bank, side)
    ic.shade(minus(ImageChops.offset(bank, 10, 16), union(bank, chan)), (16, 22, 6), 0.5, blur=5)  # cast on the field
    earth(ic, crest, "#a6a060", "#6a6634", span=(BACK, FRONT))
    lay, d = layer()
    R = ic.random
    for _ in range(900):
        x, y = R.uniform(24, 1000), R.uniform(BACK, FACE)
        t = R.uniform(-1, 1)
        col = (150, 176, 80, 210) if t > -0.3 else (60, 80, 26, 200)
        d.line([(x, y), (x + R.uniform(-4, 4), y - R.uniform(6, 16))], fill=col, width=3)
    composite(ic, lay, crest)
    ic.shade(minus(crest, ImageChops.offset(crest, 0, 10)), (255, 244, 200), 0.28, blur=2)  # lit top edge
    ic.shade(ic.intersect(crest, ImageChops.offset(side, 0, -8)), (30, 24, 10), 0.3, blur=4)  # crest rolls over
    earth(ic, side, "#6e5032", "#34240e", span=(BACK, FACE))
    ic.shade(ic.intersect(side, ImageChops.offset(chan, -6, -10)), (16, 10, 4), 0.35, blur=4)
    # water: darker at the back, lighter where the arms open out
    ic.fill(chan, "#5e98a8", W_DEEP, (BACK - 60, FACE + 60), noise=0.08, chroma=0.06)
    ic.shade(ic.intersect(chan, ic.mask("rectangle", (0, 0, SIZE, FORK[1] + 30))), (14, 40, 52), 0.3, blur=24)
    # the shed's reflection in the channel head
    ic.shade(ic.intersect(chan, ic.mask("rectangle", (SHED[0] + 12, BACK - 10, SHED[1] - 12, BACK + 70))), (70, 50, 26),
             0.55, blur=8)
    ic.shade(ic.intersect(chan, ic.mask("rectangle", (SHED[0] + 58, BACK, SHED[0] + 114, BACK + 50))), (16, 12, 8), 0.55, blur=6)
    ic.shade(ic.intersect(chan, ImageChops.offset(bank, 12, 14)), (8, 22, 30), 0.5, blur=6)  # bank shadow on the water
    x0, y0, x1, y1 = chan.getbbox()
    ripples(ic, chan, y0 + 20, y1, x0, x1, 1700)
    ic.shade(minus(chan.filter(ImageFilter.MaxFilter(9)), chan), (22, 16, 8), 0.6)  # wet line at the water
    # wattle stakes along the waterline of both arms near the fork
    for path, w0, w1 in ((LEFT, 104, 180), (RIGHT, 104, 180)):
        for i in range(2, len(path) - 4, 3):
            x, y = path[i]
            for sd in (-1, 1):
                sx = x + (w0 + (w1 - w0) * i / len(path)) / 2 * sd + 2 * sd
                ic.line([(sx, y - 16), (sx, y + 12)], 10, (44, 30, 18))
                ic.line([(sx - 3, y - 14), (sx - 3, y + 8)], 3, (150, 116, 76, 170))
    # reeds on the island tip and along the outer embankments
    reeds(ic, 450, 540, FORK[1] + 66, 90, heads=0.3)
    reeds(ic, 24, 80, FRONT + 10, 110)
    reeds(ic, 350, 420, FRONT + 20, 100)
    reeds(ic, 590, 660, FRONT + 20, 100)
    reeds(ic, 944, 1000, FRONT + 10, 110)
    sampan(ic, 650, 512, 1.2)
    rim_darken(ic)


def sampan(ic: Icon, cx: float, wl: float, k: float = 1.0) -> None:
    """Small sampan with a mat-roofed middle, a boatman poling at the stern."""
    L = 200 * k
    x0, x1 = cx - L / 2, cx + L / 2
    ts = np.linspace(0, 1, 24)
    top = [(x0 + L * t, wl - k * (22 - 10 * math.sin(math.pi * t) + 26 * (1 - t) ** 5 + 22 * t ** 5)) for t in ts]
    hull = top + [(x1 - 20 * k, wl + 10 * k), (x0 + 20 * k, wl + 10 * k)]
    ic.shade(ic.mask("ellipse", (x0 + 10, wl - 4, x1 + 30, wl + 26)), (8, 22, 30), 0.4, blur=8)
    # mat roof (half barrel)
    mx0, mx1 = cx - 50 * k, cx + 40 * k
    roof = [(mx0, wl - 20 * k)] + [(mx0 + (mx1 - mx0) * t, wl - k * (20 + 58 * math.sin(math.pi * t) ** 0.8)) for t in ts] + \
        [(mx1, wl - 20 * k)]
    rm = ic.poly_mask(roof)
    ic.fill(rm, "#b89660", "#5a4428", (mx0, mx1), vertical=False, noise=0.3)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (cx, 0, SIZE, SIZE))), (20, 12, 4), 0.25, blur=8)
    for j in range(1, 6):
        xx = mx0 + (mx1 - mx0) * j / 6
        ic.line([(xx, wl - 22 * k), (xx, wl - k * (20 + 56 * math.sin(math.pi * j / 6) ** 0.8))], 3, (60, 44, 24, 160))
    ic.outline(roof, 4)
    hm = planks(ic, hull, "#7e5c3a", "#40301c", board=12 * k, vertical_boards=False)
    ic.line(top, int(8 * k), (58, 40, 26))
    ic.line([(x, y - 3) for x, y in top], 3, (180, 140, 96, 150))
    ic.outline(hull, 4, (40, 26, 16, 190))
    # boatman with a pole
    bx = x1 - 36 * k
    ic.line([(bx - 60 * k, wl - 150 * k), (bx + 40 * k, wl + 30 * k)], int(6 * k), (110, 86, 56))
    ic.poly([(bx - 14 * k, wl - 30 * k), (bx + 12 * k, wl - 30 * k), (bx + 8 * k, wl - 86 * k), (bx - 10 * k, wl - 86 * k)],
            "#4e5a6a", "#2a303a", edge=4)
    ic.fill(ic.mask("ellipse", (bx - 12 * k, wl - 112 * k, bx + 12 * k, wl - 86 * k)), "#b08460", "#6a4a30", noise=0.1)
    ic.poly([(bx - 34 * k, wl - 100 * k), (bx + 34 * k, wl - 100 * k), (bx, wl - 126 * k)], "#c4a870", "#7a6438", edge=4)
    ic.line([(bx - 6 * k, wl - 70 * k), (bx - 34 * k, wl - 104 * k)], int(8 * k), (176, 132, 96))
    ic.waterline(hm, wl + 2)
