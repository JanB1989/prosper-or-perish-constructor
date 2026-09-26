"""River Navigation Works (river_navigation_works): a kept river channel with its towpath and a groyne.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the worked river bank. A draught horse on the towpath hauls a laden river barge by a line
from its mast; the grassed bank is held at the water by a pile-and-wattle revetment, and a
stone-filled pile groyne juts out towards the viewer with the current breaking white against it.
Unlike the vanilla river works (locks, wheels, bridges) there is no building: the bank itself is
the works.
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


def lap(ic: Icon, x0: float, x1: float, y: float, clip: Image.Image | None = None, dens: float = 1.0) -> None:
    """Irregular lapping foam along a waterline: short broken strokes of varied length, width and gap."""
    R = ic.random
    lay, d = layer()
    x = x0 + R.uniform(0, 20)
    while x < x1:
        L = R.uniform(10, 46)
        yy = y + R.uniform(-5, 7)
        w = R.choice((4, 5, 6, 8))
        d.line([(x, yy), (x + L * 0.5, yy - R.uniform(0, 3)), (x + L, yy + R.uniform(-2, 2))],
               fill=(232, 244, 245, R.randint(150, 235)), width=w, joint="curve")
        x += L + R.uniform(8, 60) / dens
    composite(ic, lay, clip)


def chaikin(pts, n: int = 2, closed: bool = True) -> list:
    """Round off a polygon's corners (Chaikin corner cutting)."""
    pts = list(pts)
    for _ in range(n):
        out = []
        m = len(pts) if closed else len(pts) - 1
        for i in range(m):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            out += [(0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by), (0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by)]
        pts = out if closed else [pts[0]] + out + [pts[-1]]
    return pts


def cobble(ic: Icon, x: float, y: float, rx: float, ry: float) -> None:
    """Rounded field stone: lit top-left, dark underside, soft rim, no facet lines."""
    pts = chaikin(ic.jitter(x, y, rx, ry, 7, 0.25), 2)
    ic.fill(ic.poly_mask(pts), "#ddd3c0", "#6e675c", radial=(x - rx * 0.6, y - ry * 0.8, max(rx, ry) * 2.2), noise=0.2)
    ic.outline(pts, 3, (46, 40, 32, 150))


def limb(ic: Icon, pts, widths, c1, c2) -> list:
    """Tapering leg along a polyline with per-point widths; vertical gradient; returns the outline."""
    left, right = [], []
    for i, (px, py) in enumerate(pts):
        q = pts[min(i + 1, len(pts) - 1)]
        p0 = pts[max(i - 1, 0)]
        vx, vy = q[0] - p0[0], q[1] - p0[1]
        vl = math.hypot(vx, vy) or 1
        nx, ny = -vy / vl, vx / vl
        hw = widths[i] / 2
        left.append((px - nx * hw, py - ny * hw))
        right.append((px + nx * hw, py + ny * hw))
    poly = chaikin(left + right[::-1], 2)
    ys = [p[1] for p in pts]
    ic.fill(ic.poly_mask(poly), c1, c2, (min(ys), max(ys)), noise=0.18)
    ic.outline(poly, 3, (26, 16, 10, 190))
    return poly


def burlap_sack(ic: Icon, cx: float, base: float, w: float, h: float, lean: float = 0) -> None:
    """Laden burlap sack: warm tone, lit left, shaded right, faint weave, gathered neck with a tie."""
    pts = [(cx - w * 0.5, base), (cx - w * 0.56, base - h * 0.45), (cx - w * 0.42, base - h * 0.78),
           (cx - w * 0.16 + lean, base - h * 0.9), (cx + w * 0.16 + lean, base - h * 0.9),
           (cx + w * 0.44, base - h * 0.76), (cx + w * 0.56, base - h * 0.42), (cx + w * 0.5, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#c09a62", "#6e4e2c", (cx - w * 0.4, cx + w * 0.6), vertical=False, noise=0.24, chroma=0.12)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx + w * 0.05, base - h * 0.9, cx + w * 0.9, base + 10))),
             (30, 18, 8), 0.35, blur=8)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - w * 0.45, base - h * 0.8, cx - w * 0.02, base - h * 0.35))),
             (255, 236, 196), 0.22, blur=8)
    lay, d = layer()
    R = ic.random
    for _ in range(int(w / 6)):
        y = R.uniform(base - h * 0.85, base)
        d.line([(cx - w * 0.6, y), (cx + w * 0.6, y + R.uniform(-3, 3))], fill=(50, 32, 16, 40), width=2)
    for _ in range(3):
        fx = cx + R.uniform(-w * 0.3, w * 0.2)
        d.line([(fx, base - h * 0.75), (fx + R.uniform(-6, 6), base - h * 0.1)], fill=(60, 40, 20, 70), width=3)
    composite(ic, lay, m)
    ic.outline(pts, 3, (40, 26, 14, 190))
    # gathered neck and tuft
    nx = cx + lean
    ny = base - h * 0.9
    ic.poly([(nx - w * 0.12, ny + 4), (nx - w * 0.08, ny - 12), (nx - w * 0.18, ny - 26), (nx, ny - 18),
             (nx + w * 0.18, ny - 28), (nx + w * 0.1, ny - 12), (nx + w * 0.13, ny + 4)], "#b89060", "#6a4a28",
            vertical=False, edge=3)
    ic.line([(nx - w * 0.14, ny - 6), (nx + w * 0.15, ny - 8)], 6, (58, 36, 18))
    ic.line([(nx + w * 0.12, ny - 7), (nx + w * 0.2, ny + 12)], 3, (58, 36, 18))


def bale(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Small bundle wrapped in matting and roped crosswise."""
    pts = ic.jitter((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, 12, 0.06)
    pts = [(x, min(y, y1)) for x, y in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, "#a89464", "#5e5030", (x0, x1), vertical=False, noise=0.26)
    ic.shade(ic.intersect(m, ic.mask("rectangle", ((x0 + x1) / 2, y0, x1 + 4, y1))), (20, 14, 6), 0.3, blur=6)
    ic.outline(pts, 3, (40, 28, 14, 190))
    for f in (0.3, 0.7):
        xx = x0 + (x1 - x0) * f
        ic.line([(xx, y0 + 3), (xx + 3, y1 - 3)], 5, (70, 46, 24))
    ic.line([(x0 + 3, (y0 + y1) / 2), (x1 - 3, (y0 + y1) / 2 + 2)], 5, (70, 46, 24))


def keg(ic: Icon, cx: float, cy: float, L: float, r: float) -> None:
    """Small cask lying on its side, end towards the viewer's left."""
    body = [(cx - L / 2, cy - r * 0.9), (cx + L / 2, cy - r * 0.9), (cx + L / 2 + 4, cy), (cx + L / 2, cy + r * 0.9),
            (cx - L / 2, cy + r * 0.9)]
    ic.poly(body, "#b07a4a", "#5a3a20", edge=3)
    for f in (0.3, 0.72):
        xx = cx - L / 2 + L * f
        ic.line([(xx, cy - r * 0.95), (xx, cy + r * 0.95)], 5, (50, 50, 54))
    ic.fill(ic.mask("ellipse", (cx - L / 2 - r * 0.45, cy - r, cx - L / 2 + r * 0.45, cy + r)), "#c49a6a", "#7a5230",
            radial=(cx - L / 2 - 4, cy - r * 0.5, r * 1.4), noise=0.2)
    ic.overlay(lambda d: d.ellipse((cx - L / 2 - r * 0.45, cy - r, cx - L / 2 + r * 0.45, cy + r), outline=(40, 26, 14, 200),
                                   width=3))


SEED = 5
REFS = ("pound_lock_canal_infrastructure", "irrigation_systems", "bridge_infrastructure", "dock")

BAND_TOP, BAND_BOT = 470, 812
PATH_TOP, PATH_BOT, BANK_FOOT = 322, 388, 488   # bank top back/front edge, bank toe in the water
TROD = 370                                      # front edge of the trodden towpath strip
BX0, BX1 = 30, 996
HORSE_X, HORSE_S, HOOF = 688, 1.42, 364


def bank(ic: Icon) -> None:
    # a low bush behind the bank, between the mast and the horse, well under the tow line
    canopy(ic, 520, 318, 74, 40, light="#86984c", dark="#34441e", n=11)
    canopy(ic, 460, 330, 40, 24, light="#7e9048", dark="#30401c", n=7)
    top = [(BX0 + 30, PATH_TOP), (BX1 - 60, PATH_TOP), (BX1 - 20, PATH_BOT), (BX0, PATH_BOT)]
    tm = ic.poly_mask(top)
    turf(ic, tm, "#8e9a56", "#5e6a32", span=(PATH_TOP, PATH_BOT), density=360)
    # the towpath: a lighter trodden strip along the back of the bank, hoof prints and a rut
    trod = [(BX0 + 34, PATH_TOP + 4), (BX1 - 62, PATH_TOP + 4), (BX1 - 44, TROD), (BX0 + 14, TROD)]
    trm = ic.intersect(tm, ic.poly_mask(trod))
    earth(ic, trm, "#d6c298", "#a88e66", span=(PATH_TOP, TROD))
    R = ic.random
    lay, d = layer()
    for _ in range(60):
        x, y = R.uniform(BX0 + 40, BX1 - 60), R.uniform(PATH_TOP + 10, TROD - 6)
        d.ellipse((x - 5, y - 3, x + 5, y + 3), fill=(80, 60, 36, R.randint(50, 100)))
    d.line([(BX0 + 40, PATH_TOP + 22), (BX1 - 60, PATH_TOP + 20)], fill=(90, 70, 44, 70), width=4)
    d.line([(BX0 + 40, PATH_TOP + 25), (BX1 - 60, PATH_TOP + 23)], fill=(255, 240, 210, 60), width=2)
    composite(ic, lay, trm)
    ic.shade(ic.mask("rectangle", (BX0, TROD - 2, BX1, TROD + 6)), (40, 50, 20), 0.3, blur=3)
    for x in range(BX0 + 30, BX1 - 40, 46):
        weeds(ic, x + R.uniform(-10, 10), TROD + 4, 26, hang=False)
    ic.outline(top, 5)
    slope = [(BX0, PATH_BOT), (BX1 - 20, PATH_BOT), (BX1 + 10, BANK_FOOT), (BX0 - 10, BANK_FOOT)]
    turf(ic, ic.poly_mask(slope), span=(PATH_BOT - 20, BANK_FOOT))
    ic.shade(ic.mask("rectangle", (BX0 - 20, PATH_BOT, BX1 + 20, PATH_BOT + 18)), alpha=0.25, blur=8)
    ic.outline(slope, 5)
    # pile-and-wattle revetment along the toe
    wat = [(BX0 - 10, BANK_FOOT - 44), (BX1 + 10, BANK_FOOT - 44), (BX1 + 10, BANK_FOOT + 20), (BX0 - 10, BANK_FOOT + 20)]
    ic.fill(ic.poly_mask(wat), "#8a7050", "#4a3a28", (BANK_FOOT - 44, BANK_FOOT + 20), noise=0.25)
    lay, d = layer()
    for k, y in enumerate(range(BANK_FOOT - 40, BANK_FOOT + 20, 12)):
        for x in range(BX0 - 10 + (k % 2) * 20, BX1 + 10, 40):
            d.arc((x, y - 6, x + 40, y + 8), 180, 360, fill=(40, 28, 16, 150), width=4)
            d.arc((x, y - 9, x + 40, y + 5), 200, 340, fill=(230, 200, 150, 60), width=3)
    composite(ic, lay, ic.poly_mask(wat))
    x = BX0 + 10
    while x < BX1:
        pile(ic, x, BANK_FOOT - 62 + ic.random.uniform(-6, 6), BANK_FOOT + 20, 26)
        x += ic.random.uniform(70, 90)
    for wx in (90, 330, 560, 900):
        weeds(ic, wx, BANK_FOOT - 46, 70)
    # a stone mile post on the path edge
    ic.poly([(404, PATH_BOT - 4), (432, PATH_BOT - 4), (430, PATH_BOT - 70), (417, PATH_BOT - 82), (405, PATH_BOT - 70)],
            "#c8bca4", "#8a806c", vertical=False, edge=4)
    ic.shade(ic.mask("ellipse", (396, PATH_BOT - 12, 450, PATH_BOT + 2)), alpha=0.35, blur=4)


def horse(ic: Icon, x: float, hoof: float, s: float) -> tuple[float, float]:
    """Dark bay draught horse leaning into its collar, walking right; returns the swingletree point."""
    def P(dx, dy):
        return (x + dx * s, hoof + dy * s)

    def PS(pts):
        return [P(*p) for p in pts]

    leg_c1, leg_c2 = "#5e3820", "#140c06"
    # contact shadow on the towpath
    ic.shade(ic.mask("ellipse", (*P(-30, -7), *P(170, 7))), alpha=0.32, blur=8)
    for hx in (4, 26, 134):
        ic.shade(ic.mask("ellipse", (*P(hx - 12, -4), *P(hx + 12, 4))), alpha=0.5, blur=3)

    def hoof_at(pts, w, dark=0.0):
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        vx, vy = bx - ax, by - ay
        vl = math.hypot(vx, vy) or 1
        vx, vy = vx / vl, vy / vl
        nx, ny = -vy, vx
        h = w * 0.62
        q = [(bx - nx * h - vx * 4, by - ny * h - vy * 4), (bx + nx * h - vx * 4, by + ny * h - vy * 4),
             (bx + nx * h * 1.2 + vx * 12, by + ny * h * 1.2 + vy * 12),
             (bx - nx * h * 1.1 + vx * 12, by - ny * h * 1.1 + vy * 12)]
        ic.poly(q, "#3a2c20", "#120c08", edge=3)
        # a little pale feathering above the hoof
        ic.shade(ic.poly_mask(ic.jitter(bx - vx * 6, by - vy * 6, w * 0.7, w * 0.4, 8, 0.3)), (190, 170, 140),
                 0.35 - dark, blur=3)

    def leg(pts, widths, far=False):
        sp = PS(pts)
        ws = [w * s for w in widths]
        poly = limb(ic, sp, ws, "#4a2c18" if far else leg_c1, leg_c2)
        if not far:
            ic.line([(px - w * 0.25, py) for (px, py), w in zip(sp[:-1], ws[:-1])], 3, (255, 220, 180, 50))
        hoof_at(sp, ws[-1], 0.15 if far else 0.0)
        return poly

    # far legs first (darker)
    leg([(46, -78), (44, -56), (36, -34), (28, -14), (24, 0)], [28, 18, 12, 10, 10], far=True)
    leg([(134, -72), (137, -50), (136, -30), (133, -12), (134, 0)], [22, 15, 12, 10, 10], far=True)
    # near legs: hind leg driving back, foreleg bent mid-stride (drawn under the body mass)
    leg([(34, -80), (30, -56), (18, -36), (8, -16), (2, 0)], [34, 22, 13, 11, 11])
    leg([(146, -74), (158, -52), (168, -36), (157, -22), (145, -16)], [26, 16, 13, 10, 10])
    # tail
    tail = PS([(8, -114), (-4, -104), (-14, -80), (-16, -58), (-8, -46), (-4, -64), (0, -88), (12, -104)])
    ic.poly(tail, "#2a1a10", "#0e0806", edge=3)
    ic.line(PS([(2, -106), (-8, -84), (-10, -60)]), 3, (120, 84, 56, 110))
    # body, neck and head in one mass
    body = chaikin(PS([(4, -106), (12, -124), (34, -132), (62, -126), (96, -119), (124, -125), (146, -150), (168, -170),
               (182, -176), (192, -172), (216, -132), (214, -120), (202, -115), (186, -126), (172, -118),
               (162, -98), (160, -80), (148, -64), (120, -58), (80, -55), (44, -61), (26, -70), (10, -86)]), 3)
    m = ic.poly_mask(body)
    ic.fill(m, "#8a5634", "#2a160a", (P(0, -134)[1], P(0, -56)[1]), noise=0.2, chroma=0.12)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, P(0, -84)[1], SIZE, SIZE))), (14, 8, 4), 0.35, blur=12)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (*P(6, -134), *P(66, -108)))), (255, 214, 166), 0.22, blur=10)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (*P(112, -136), *P(150, -100)))), (255, 214, 166), 0.16, blur=10)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (*P(26, -104), *P(70, -66)))), (14, 8, 4), 0.25, blur=12)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (*P(96, -112), *P(126, -62)))), (14, 8, 4), 0.2, blur=12)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (*P(196, -134), *P(220, -112)))), (10, 6, 4), 0.45, blur=5)
    ic.outline(body, 3, (26, 16, 10, 200))
    # gaskin and forearm muscles continue the near legs up into the body
    ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(*P(34, -76), 16 * s, 12 * s, 8, 0.15))), (255, 214, 166), 0.12, blur=6)
    ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(*P(148, -70), 12 * s, 9 * s, 8, 0.15))), (255, 214, 166), 0.12, blur=6)
    # mane, ear, eye and bridle
    ic.poly(PS([(118, -124), (144, -154), (168, -174), (184, -180), (178, -168), (152, -144), (126, -118)]),
            "#24160c", "#0c0804", edge=0)
    ic.poly(PS([(178, -172), (178, -192), (188, -176)]), "#5a3620", "#24140a", edge=3)
    ex, ey = P(194, -154)
    ic.draw.ellipse((ex - 5, ey - 4, ex + 5, ey + 4), fill=(14, 10, 8, 255))
    ic.line([P(184, -168), P(204, -126)], 4, (30, 20, 12))
    ic.line([P(198, -130), P(216, -128)], 4, (30, 20, 12))
    # collar with hames, backpad and traces running back to the swingletree
    ic.line(PS([(142, -154), (156, -130), (166, -104), (162, -82)]), int(16 * s), (48, 30, 18))
    ic.line(PS([(139, -150), (152, -128), (161, -104)]), int(5 * s), (130, 92, 58, 190))
    ic.line(PS([(150, -160), (164, -130), (172, -100), (168, -82)]), int(3 * s), (176, 146, 86))
    ic.line(PS([(96, -122), (94, -60)]), int(8 * s), (40, 26, 16))
    ic.line(PS([(96, -123), (95, -104)]), int(3 * s), (130, 92, 58, 160))
    ic.line(PS([(162, -100), (96, -96), (30, -96), (-18, -96)]), int(5 * s), (36, 24, 14))
    ic.line(PS([(-18, -110), (-16, -82)]), int(6 * s), (110, 80, 50))
    return P(-17, -96)


def barge(ic: Icon, bx0: float, bx1: float, gun: float, wl: float) -> tuple[Image.Image, tuple[float, float]]:
    """River barge with a mast, furled sail, cargo and a stern cabin; returns hull mask and mast head."""
    L = bx1 - bx0
    mast = bx0 + L * 0.40
    top_y = 96
    timber(ic, (mast, gun + 10), (mast + 4, top_y), 26, "#8e6a48", "#4e3824")
    yard = 176
    # furled sail: an ochre canvas roll under the yard, lit top, shadowed underside, gaskets round it
    ts = np.linspace(0, 1, 26)
    ts = np.linspace(0, 1, 60)
    up = [(mast - 128 + 268 * t, yard + 4 - 3 * math.sin(math.pi * t) + 12 * t) for t in ts]
    lo = [(mast - 128 + 268 * t, yard + 26 + 8 * math.sin(math.pi * t) + 4 * abs(math.sin(5 * math.pi * t)) + 12 * t)
          for t in ts]
    roll = up + lo[::-1]
    rm = ic.poly_mask(roll)
    ic.fill(rm, "#dcb46e", "#8a602c", (yard + 4, yard + 50), noise=0.22, chroma=0.12)
    ic.shade(ic.intersect(rm, ic.poly_mask([(x, y + 18) for x, y in up] + lo[::-1])), (50, 26, 6), 0.42, blur=5)
    ic.line([(x, y + 7) for x, y in up[2:-2]], 4, (255, 236, 190, 120))
    for k in range(6):
        t = k * 0.2
        gx = mast - 128 + 268 * t
        if 0 < t < 1:
            ic.line([(gx - 2, yard + 2 + 12 * t), (gx + 2, yard + 30 + 8 * math.sin(math.pi * t) + 12 * t)], 6, (70, 46, 22))
    ic.outline(roll, 4)
    timber(ic, (mast - 140, yard + 6), (mast + 150, yard + 12), 14, "#7a5838", "#4a321f")
    ic.line([(mast, top_y + 14), (bx0 + 10, gun - 20)], 4, (58, 40, 26))
    ic.line([(mast, top_y + 14), (bx1 - 6, gun - 6)], 4, (58, 40, 26))
    ts = np.linspace(0, 1, 30)
    top = [(bx0 + L * t, gun + 12 * math.sin(math.pi * t) - 26 * (1 - t) ** 6 - 12 * t ** 8) for t in ts]
    hull = [(bx0 - 28, gun - 28)] + top + [(bx1 + 16, gun - 16), (bx1 + 4, wl + 18), (bx0 + 40, wl + 18)]
    far = [(x + 6, y - 26) for x, y in top]
    ic.poly(far + top[::-1], "#4c3524", "#35251a", edge=0)
    # cargo: two burlap sacks, a roped bale, the water cask and a keg lying at the bow
    burlap_sack(ic, bx0 + L * 0.13, gun + 6, 74, 78, lean=-4)
    burlap_sack(ic, bx0 + L * 0.26, gun + 8, 70, 88, lean=5)
    bale(ic, bx0 + L * 0.31, gun - 40, bx0 + L * 0.40, gun + 6)
    ic.barrel(bx0 + L * 0.47, gun - 74, bx0 + L * 0.47 + 60, gun + 6)
    keg(ic, bx0 + L * 0.07, gun - 16, 46, 22)
    cx0, cx1 = bx0 + L * 0.64, bx0 + L * 0.94
    planks(ic, [(cx0, gun - 86), (cx1, gun - 86), (cx1, gun + 6), (cx0, gun + 6)], "#a4845c", "#5a4430", board=20)
    ic.poly([(cx0 - 18, gun - 80), (cx1 + 18, gun - 80), (cx1 + 4, gun - 122), (cx0 - 4, gun - 122)], "#7a5a3c", "#4a3422",
            edge=4)
    ic.shade(ic.mask("rectangle", (cx0, gun - 80, cx1, gun - 60)), alpha=0.4, blur=5)
    ic.rect((cx0 + 26, gun - 58, cx0 + 60, gun - 24), "#2a2420", "#18140f", edge=3)
    hm = planks(ic, hull, "#8e6842", "#4a3220", board=18, vertical_boards=False)
    ic.shade(ic.intersect(hm, ic.mask("rectangle", (bx0 - 30, wl - 16, bx1 + 20, wl + 20))), alpha=0.4, blur=10)
    ic.shade(ic.intersect(hm, ic.mask("rectangle", (bx1 - 110, 0, SIZE, SIZE))), alpha=0.2, blur=20)
    ic.line(top, 12, (58, 40, 26))
    ic.line([(x, y - 3) for x, y in top], 5, (176, 136, 94, 170))
    ic.outline(hull, 4, (40, 26, 16, 190))
    timber(ic, (bx1 + 10, gun - 12), (bx1 + 20, wl + 8), 16)
    return hm, (mast + 2, top_y + 30)


def groyne(ic: Icon, band_m: Image.Image) -> None:
    """Stone-filled pile groyne angled out into the stream from the bank: lit top face, shadowed
    upstream side, a foam wedge where the current piles against it and a short wake off its head."""
    F, N = (842, BANK_FOOT + 2), (702, 766)

    def C(t):
        return F[0] + (N[0] - F[0]) * t, F[1] + (N[1] - F[1]) * t

    def hw(t):
        return 40 + 22 * t

    def ht(t):
        return 22 + 28 * t

    def Lt(t, top=True):
        x, y = C(t)
        return (x - hw(t), y - (ht(t) if top else 0))

    def Rt(t, top=True):
        x, y = C(t)
        return (x + hw(t), y - (ht(t) if top else 0))

    # cast shadow on the water to the right (light from the upper left)
    ic.shade(ic.intersect(band_m, ic.poly_mask([Rt(0, False), (Rt(0, False)[0] + 50, Rt(0, False)[1]),
                                                (Rt(1, False)[0] + 70, Rt(1, False)[1] + 14), Rt(1, False)])),
             (8, 26, 36), 0.35, blur=12)
    side = [Rt(0), Rt(1), Rt(1, False), Rt(0, False)]
    head = [Lt(1), Rt(1), Rt(1, False), Lt(1, False)]
    topf = [Lt(0), Rt(0), Rt(1), Lt(1)]
    # shadowed upstream side and the head: coursed stone behind the piles
    sm = ic.poly_mask(side)
    ic.fill(sm, "#6a6052", "#302a24", (F[1], N[1]), noise=0.24)
    lay, d = layer()
    R = ic.random
    for k in range(14):
        t = k / 13
        x, y = Rt(t, False)
        d.line([Rt(t)[0], Rt(t)[1] + 6, x, y - 4], fill=(20, 16, 12, 90), width=3)
        d.line([(x - 6, y - ht(t) * R.uniform(0.3, 0.7)), (x + 14, y - ht(t) * R.uniform(0.3, 0.7) + 20)],
               fill=(150, 140, 120, 50), width=3)
    composite(ic, lay, sm)
    ic.outline(side, 4)
    hm = ic.poly_mask(head)
    ic.fill(hm, "#8a7e6a", "#4c443a", (Lt(1)[1], N[1]), noise=0.24)
    ic.shade(ic.intersect(hm, ic.mask("rectangle", (0, N[1] - 16, SIZE, SIZE))), (14, 20, 20), 0.35, blur=6)
    ic.outline(head, 4)
    # lit top face: pale rubble between the pile rows
    tm = ic.poly_mask(topf)
    earth(ic, tm, "#cabfa8", "#8e8474", span=(F[1] - 30, N[1] - 40))
    stones = []
    for _ in range(26):
        t = R.random()
        x0, y0 = Lt(t)
        x1, _ = Rt(t)
        stones.append((y0, R.uniform(x0 + 16, x1 - 16), 0.6 + 0.6 * t))
    for y, x, s in sorted(stones):
        cobble(ic, x, y + 4 * s, 22 * s, 12 * s)
    ic.shade(ic.intersect(tm, ic.poly_mask([Rt(0), Rt(1), (Rt(1)[0] - 36, Rt(1)[1]), (Rt(0)[0] - 26, Rt(0)[1])])),
             (20, 16, 10), 0.28, blur=10)
    ic.shade(ic.intersect(tm, ic.poly_mask([Lt(0), Lt(1), (Lt(1)[0] + 40, Lt(1)[1]), (Lt(0)[0] + 30, Lt(0)[1])])),
             (255, 246, 222), 0.2, blur=10)
    ic.outline(topf, 4)
    # pile heads catch the light along both edges; the upstream row stands in the water
    for k in range(7):
        t = k / 6
        w = 22 + 16 * t
        x, y = Lt(t)
        pile(ic, x + 8, y - 8 - 4 * t, y + 8, w * 0.9, "#b0906a", "#5a4430")
    for k in range(7):
        t = k / 6
        w = 24 + 18 * t
        x, y = Rt(t)
        yw = Rt(t, False)[1]
        pile(ic, x - 4, y - 18 - 6 * t, yw + 4, w, "#9a7a54", "#3e2c1c")
        ic.shade(ic.mask("rectangle", (x - 4, y + 10, x - 4 + w / 2, yw + 4)), (10, 8, 6), 0.35, blur=3)
    for x in (Lt(1)[0] + 30, C(1)[0] + 6):
        pile(ic, x, Lt(1)[1] - 14, N[1] + 4, 40, "#a8865e", "#5a4430")
    # wet dark line at the water
    ic.line([Lt(1, False), Rt(1, False), Rt(0, False)], 6, (24, 30, 30, 170))
    # foam wedge piled against the upstream face, thickest at the head
    lay, d = layer()
    ts = np.linspace(0.08, 1.0, 16)
    outer = []
    inner = []
    for t in ts:
        x, y = Rt(t, False)
        wdt = 4 + 20 * t ** 1.6
        outer.append((x + wdt * R.uniform(0.7, 1.3) + 4, y + R.uniform(-2, 4)))
        inner.append((x + 2, y - 3 - 6 * t))
    hx, hy = Rt(1, False)
    tipx, tipy = Lt(1, False)
    for i in range(len(ts) - 1):
        if ts[i] < 0.7 and R.random() < 0.35:
            continue
        d.polygon([inner[i], inner[i + 1], outer[i + 1], outer[i]], fill=(236, 246, 246, 225))
    d.polygon([inner[-1], outer[-1], (hx + 24, hy + 12), (hx - 4, hy + 16), (tipx + 12, tipy + 10), (tipx + 18, tipy - 2)],
              fill=(236, 246, 246, 225))
    for t in ts[::2]:
        x, y = Rt(t, False)
        d.line([(x + 6, y + 2), (x + 10 + 20 * t, y + 4)], fill=(120, 160, 170, 150), width=3)
    composite(ic, lay, band_m)
    # short V-wake trailing downstream (left) off the head
    lay, d = layer()
    ax, ay = tipx - 4, tipy + 6
    for (ex, ey), w, a in (((ax - 84, ay - 20), 7, 220), ((ax - 74, ay + 24), 7, 220)):
        for t0, t1 in ((0.0, 0.45), (0.58, 0.8), (0.9, 1.0)):
            pts = [(ax + (ex - ax) * t, ay + (ey - ay) * t + 4 * math.sin(math.pi * t)) for t in np.linspace(t0, t1, 5)]
            d.line(pts, fill=(234, 244, 245, int(a * (1 - 0.4 * t0))), width=max(3, int(w * (1 - 0.5 * t0))), joint="curve")
    composite(ic, lay, band_m)


def draw(ic: Icon) -> None:
    b = band(ic, BAND_TOP, BAND_BOT, x0=18, x1=1006, inset=24, sag=26)
    bank(ic)
    hx, hy = horse(ic, HORSE_X, HOOF, HORSE_S)
    ic.waterline(ic.mask("rectangle", (0, 400, SIZE, SIZE)), BANK_FOOT - 4)
    # the bank shades the water along its foot
    ic.shade(ic.intersect(b, ic.mask("rectangle", (0, BANK_FOOT - 6, SIZE, BANK_FOOT + 34))), (8, 24, 34), 0.4, blur=12)
    lap(ic, 40, 980, BANK_FOOT - 2, b)
    hull, (mx, my) = barge(ic, 70, 560, 590, 676)
    ic.waterline(hull.filter(ImageFilter.MaxFilter(9)), 660)
    # a faint broken reflection of the hull
    refl = ic.poly_mask([(60, 662), (590, 662), (560, 700), (120, 704)])
    ic.shade(ic.intersect(refl, b), (48, 32, 18), 0.32, blur=8)
    lay, d = layer()
    R = ic.random
    for y in range(668, 712, 9):
        x = 70 + R.uniform(0, 40)
        while x < 580:
            L = R.uniform(40, 110)
            d.line([(x, y), (x + L, y + R.uniform(-1, 1))], fill=(130, 186, 200, 110), width=3)
            x += L + R.uniform(20, 60)
    composite(ic, lay, b)
    lap(ic, 60, 590, 661, b, dens=1.4)
    ts = np.linspace(0, 1, 24)
    ic.line([(mx + (hx - mx) * t, my + (hy - my) * t + 40 * math.sin(math.pi * t)) for t in ts], 7, (70, 52, 34))
    groyne(ic, b)
    rim_darken(ic)
