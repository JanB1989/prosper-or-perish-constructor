"""Sand Washery (sand_washery): a drum screen and a washing trough on trestles over heaps of clean sand.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/sand_washery/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/sand_washery

Identity: water. A thick plank flume on two trestles brings a stream in from the left into a drum
screen of spaced bars with iron end rings (the riddle screens slot) sheltered under a board roof;
sand falls through the bars into a long trough on trestles that runs into a plank settling tank
(clear water over settled sand), while the screened-out gravel drops from the drum's low end
straight onto a grey gravel heap. A low sluice box sits on the ground under the trestles; in front
lie slumped heaps of pale, clean sand, one cut by a shovel. Vanilla sand_pit (treadwheel crane over
sand cones) is the tier before; this one reads through the flowing water, the drum and the long
trough. Local helpers: ``union``, ``tint``, ``paste_clipped``, ``timber``, ``planks``, ``shingles``
(copied), new ``trough``, ``drum``, ``gravel_fall``, ``sand_rain``, ``sand_heap``, ``sluice``,
``tank``, ``stream``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 5
REFS = ("sand_pit", "irrigation_systems", "glass_workshop", "sawmill")

WOOD, WOOD_DK = "#8a6240", "#4c3422"
W_LIGHT, W_DEEP = "#86bccb", "#2e6274"
SAND, SAND_DK = "#ebcf8a", "#94692e"
GROUND = 830
ANG = math.atan2(150, 560)  # trough slope
DX, DY = math.cos(ANG), math.sin(ANG)


# ---------------------------------------------------------------- helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
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


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, along: tuple[float, float] | None = None) -> Image.Image:
    """Board panel: per-board tone, grain strokes, soft joints. Boards run vertically, or along the
    direction ``along`` (dx, dy) as long sloping boards. Returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if along:
        ax, ay = along
        v = min(ys) - (max(xs) - min(xs)) * abs(ay / ax)
        while v < max(ys):
            w = board * R.uniform(0.8, 1.2)
            t = R.uniform(-1, 1)
            col = (255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t))
            x0, x1 = min(xs) - 10, max(xs) + 10
            y0, y1 = v, v + (x1 - x0) * ay / ax
            d.polygon([(x0, y0), (x1, y1), (x1, y1 + w), (x0, y0 + w)], fill=col)
            d.line([(x0, y0), (x1, y1)], fill=(35, 22, 12, 130), width=3)
            v += w
    else:
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


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles/boards: per-tile tone, lit lower lip, soft course shadow."""
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
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def flow(ic: Icon, m: Image.Image, x0: float, x1: float, y0: float, slope: float, n: int = 40) -> None:
    """White flow streaks along a sloping water strip (``slope`` = dy/dx), clipped to ``m``."""
    R = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for _ in range(n):
            x = R.uniform(x0 - 40, x1)
            L = R.uniform(30, 90)
            off = R.uniform(-10, 40)
            y = y0 + (x - x0) * slope + off
            d.line([(x, y), (x + L, y + L * slope)], fill=(236, 246, 247, R.randint(120, 210)), width=R.choice((4, 5, 6)))
            d.line([(x + 6, y + 7), (x + L - 6, y + 7 + L * slope)], fill=(20, 50, 64, 90), width=3)

    ic.overlay(paint, m)


def trough(ic: Icon, a, b, open_w: float = 40, face: float = 56) -> Image.Image:
    """Sloping plank washing trough from ``a`` to ``b`` (far top edge): water strip seen from above,
    boarded near side. Returns the water mask."""
    (ax, ay), (bx, by) = a, b
    far = [(ax, ay), (bx, by), (bx, by + open_w), (ax, ay + open_w)]
    near = [(ax, ay + open_w), (bx, by + open_w), (bx, by + open_w + face), (ax, ay + open_w + face)]
    ic.fill(ic.poly_mask([(ax, ay - 12), (bx, by - 12), (bx, by), (ax, ay)]), "#6e4e32", "#3e2a1a", noise=0.2)  # far side board
    wm = ic.poly_mask(far)
    ic.fill(wm, W_LIGHT, W_DEEP, (ay, by + open_w), noise=0.1)
    tint(ic, ic.poly_mask([(ax, ay), (bx, by), (bx, by + 14), (ax, ay + 14)]), wm, (20, 30, 34), 0.45, 4)
    flow(ic, wm, ax, bx, ay + 6, (by - ay) / (bx - ax), n=int((bx - ax) / 12))
    planks(ic, near, "#94704a", "#553a24", board=18, along=(bx - ax, by - ay))
    ic.line([(ax, ay + open_w), (bx, by + open_w)], 8, (176, 138, 96))  # lit near rim
    ic.line([(ax, ay + open_w + 5), (bx, by + open_w + 5)], 3, (40, 26, 16, 170))
    ic.outline(near, 4, (40, 26, 16, 170))
    for t in np.linspace(0.08, 0.92, 4):  # cleats
        x, y = ax + (bx - ax) * t, ay + (by - ay) * t
        ic.line([(x, y + open_w + 4), (x, y + open_w + face - 4)], 9, (70, 48, 30, 200))
    return wm


def drum(ic: Icon, c, L: float, R: float) -> tuple[float, float]:
    """Drum screen lying along the trough slope: a straight cylinder of spaced bars with the dark
    inside showing through, thin mesh hoops, two iron end rings, a central axle stub at the low end.
    Returns the point under the low end where the screened-out gravel drops."""
    d = np.array([DX, DY])
    n = np.array([-DY, DX])
    C = np.array(c, float)
    fore = 0.3  # foreshortening of the end circles along the axis

    def ring(e, a0=0.0, a1=2 * math.pi, k: int = 36):
        return [tuple(e + d * R * fore * math.cos(t) + n * R * math.sin(t)) for t in np.linspace(a0, a1, k)]

    e0, e1 = C - d * L, C + d * L
    body = [tuple(e0 - n * R), tuple(e1 - n * R), tuple(e1 + n * R), tuple(e0 + n * R)]
    bm = union(ic.poly_mask(body), ic.poly_mask(ring(e0)), ic.poly_mask(ring(e1)))
    ic.fill(bm, "#2a2018", "#0e0a06", (C[1] - R, C[1] + R), noise=0.1)  # dark inside
    # far bars seen through the gaps
    ic.overlay(lambda dr: [dr.line([tuple(e0 + n * R * math.sin(t) * 0.9), tuple(e1 + n * R * math.sin(t) * 0.9)],
                                   fill=(80, 64, 44, 90), width=4) for t in np.linspace(-1.1, 1.1, 7)], bm)
    # near bars: straight, evenly spaced round the drum, lit on top and darker below
    for t in np.linspace(-1.25, 1.25, 8):
        off = n * R * math.sin(t)
        w = 3 + 5 * math.cos(t)
        k = (math.sin(t) + 1) / 2  # 0 top .. 1 bottom
        p0, p1 = e0 + off, e1 + off
        m = ic.intersect(ic.poly_mask([tuple(p0 - n * w / 2), tuple(p1 - n * w / 2), tuple(p1 + n * w / 2),
                                       tuple(p0 + n * w / 2)]), bm)
        c1 = tuple(int(v) for v in np.array([196, 160, 112]) * (1 - k) + np.array([92, 66, 42]) * k)
        ic.fill(m, c1, tuple(int(v * 0.7) for v in c1), (C[1] - R, C[1] + R), noise=0.14)
    # thin mesh hoops across the drum
    for f in np.linspace(-0.66, 0.66, 5):
        ic.line(ring(C + d * L * f, -math.pi / 2, math.pi / 2, 20), 4, (40, 38, 38, 200))
    # iron end rings: the high end shows its near half, the low end its whole open ring
    ic.line(ring(e0, -math.pi / 2, math.pi / 2, 24), 16, (52, 50, 50))
    ic.line([(x - 2, y - 3) for x, y in ring(e0, -math.pi / 2, 0.2, 12)], 4, (168, 164, 156, 170))
    ic.fill(ic.poly_mask(ring(e1)), "#1a120c", "#0a0604", noise=0.05)
    for a in np.linspace(0, math.pi, 3, endpoint=False):  # spokes
        p = e1 + d * R * fore * math.cos(a) + n * R * math.sin(a)
        q = e1 - d * R * fore * math.cos(a) - n * R * math.sin(a)
        ic.line([tuple(p), tuple(q)], 7, (70, 64, 58))
    ic.line(ring(e1), 16, (56, 54, 54))
    ic.line([(x - 2, y - 3) for x, y in ring(e1, math.pi * 0.9, math.pi * 1.6, 12)], 4, (172, 168, 160, 170))
    # axle stub and hub
    a0, a1 = e1 - d * 6, e1 + d * 46
    ic.line([tuple(a0), tuple(a1)], 20, (46, 44, 44))
    ic.line([tuple(a0 - n * 5), tuple(a1 - n * 5)], 4, (150, 146, 140, 170))
    ic.draw.ellipse((a1[0] - 10, a1[1] - 12, a1[0] + 10, a1[1] + 12), fill=(30, 28, 28, 255))
    ic.draw.ellipse((e1[0] - 16, e1[1] - 16, e1[0] + 16, e1[1] + 16), fill=(62, 58, 56, 255))
    # overall cylinder shading along the whole length: lit top band, shaded underside
    tint(ic, ic.poly_mask([tuple(e0 - n * R), tuple(e1 - n * R), tuple(e1 - n * R * 0.45), tuple(e0 - n * R * 0.45)]),
         bm, (255, 236, 200), 0.16, 6)
    tint(ic, ic.poly_mask([tuple(e0 + n * R * 0.35), tuple(e1 + n * R * 0.35), tuple(e1 + n * R * 1.1),
                           tuple(e0 + n * R * 1.1)]), bm, (14, 8, 4), 0.35, 8)
    ic.outline(body, 3, (40, 26, 16, 150))
    drop = e1 + n * R * 0.72 - d * 6
    return float(drop[0]), float(drop[1])


def gravel_fall(ic: Icon, x: float, y0: float, y1: float) -> None:
    """Gravel dropping straight down out of the drum's low end onto the heap below."""
    R = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for _ in range(70):
            f = R.random() ** 1.3
            y = y0 + (y1 - y0) * f
            sx = x + R.uniform(-1, 1) * (8 + 18 * f)
            r = R.uniform(4, 9)
            g = R.randint(96, 170)
            d.ellipse((sx - r, y - r * 0.8, sx + r, y + r * 0.8), fill=(g, g - 4, g - 12, 235))
            d.arc((sx - r, y - r * 0.8, sx + r, y + r * 0.8), 200, 330, fill=(236, 232, 222, 190), width=2)
            d.arc((sx - r, y - r * 0.8, sx + r, y + r * 0.8), 20, 150, fill=(30, 28, 26, 170), width=2)

    ic.overlay(paint)


def sand_rain(ic: Icon, x0: float, x1: float, top_at, bottom_at) -> None:
    """Fine sand falling through the screen into the trough below."""
    R = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for _ in range(26):
            x = R.uniform(x0, x1)
            ya, yb = top_at(x), bottom_at(x)
            if yb - ya < 8:
                continue
            y = R.uniform(ya, ya + (yb - ya) * 0.4)
            d.line([(x, y), (x + R.uniform(-2, 2), min(yb, y + R.uniform(14, 34)))], fill=(226, 196, 132, 200), width=3)

    ic.overlay(paint)


def stream(ic: Icon, x: float, y: float, dx: float, dy: float, w: float, col=(214, 234, 238)) -> None:
    """Falling stream (water or wet sand) from (x, y) with a splash."""
    ts = np.linspace(0, 1, 14)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    c = tuple(col)

    def paint(d: ImageDraw.ImageDraw) -> None:
        d.line(path, fill=(120, 170, 186, 220), width=int(w + 8), joint="curve")
        d.line(path, fill=c + (240,), width=int(w), joint="curve")
        d.line([(px - 2, py) for px, py in path[2:]], fill=(255, 255, 255, 170), width=max(3, int(w * 0.3)))
        ex, ey = path[-1]
        for _ in range(8):
            r = ic.random.uniform(4, 9)
            sx, sy = ex + ic.random.uniform(-w * 2, w * 2), ey + ic.random.uniform(-w, w * 0.3)
            d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(240, 248, 248, 200))

    ic.overlay(paint)


def smooth(pts, n: int = 2, closed: bool = False):
    """Chaikin corner cutting (keeps the end points of an open line)."""
    pts = [tuple(p) for p in pts]
    for _ in range(n):
        out = [pts[0]] if not closed else []
        rng = range(len(pts)) if closed else range(len(pts) - 1)
        for i in rng:
            p, q = pts[i], pts[(i + 1) % len(pts)]
            out += [(p[0] * 0.75 + q[0] * 0.25, p[1] * 0.75 + q[1] * 0.25), (p[0] * 0.25 + q[0] * 0.75, p[1] * 0.25 + q[1] * 0.75)]
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def sand_heap(ic: Icon, x0: float, x1: float, base: float, top: float, colors=(SAND, SAND_DK), grain=(255, 246, 220),
              pebbles: bool = False, peak: float = 0.46, notch: float | None = None) -> Image.Image:
    """Slumped heap of loose sand (or gravel): wide base, concave lower flanks, a soft irregular crest,
    lit left flank, shaded right flank, grain speckle, slip streaks, grains trickled out at the foot.
    ``notch`` = fraction along the right flank where a shovel has cut into it. Returns the mask."""
    R = ic.random
    cx = x0 + (x1 - x0) * peak
    H = base - top
    ph = R.uniform(0, 6)
    left, right = [], []
    def prof(t: float, a: float, b: float, wob: float) -> float:
        # t = 0 at the foot, 1 at the crest: rounded crest, concave slumped foot, a little waviness
        u = 1 - t
        return (1 - u ** a) ** b + wob * math.sin(t * 8 + ph) * t * u * 4

    for t in np.linspace(0, 1, 30):
        left.append((x0 + (cx - x0) * t, base - H * prof(t, 1.7, 1.6, 0.03)))
    for t in np.linspace(1, 0, 30):
        h = prof(t, 1.5, 1.35, 0.04) + 0.05 * math.sin(math.pi * t) * (1 - t)
        x, y = x1 - (x1 - cx) * t, base - H * min(h, 1.0)
        if notch is not None and abs((1 - t) - notch) < 0.12:  # shovel bite: a step down into the flank
            k = 1 - abs((1 - t) - notch) / 0.12
            x -= 26 * k
            y += 34 * k
        right.append((x, y))
    pts = smooth(left + right, 2)
    m = ic.poly_mask(pts)
    ic.fill(m, colors[0], colors[1], radial=(x0 + (cx - x0) * 0.45, top - 20, (x1 - x0) * 0.85), noise=0.2, chroma=0.08)
    tint(ic, ic.poly_mask([(cx, top), (x1 + 20, base), (cx + 30, base + 10), (cx - 10, top + 50)]), m, (40, 22, 6), 0.34, 30)
    tint(ic, ic.poly_mask([(cx - 16, top), (x0 + 30, base), (cx - 40, base)]), m, (255, 222, 160), 0.26, 24)
    if notch is not None:  # fresh cut: damp, darker, a lit lip above
        nt = notch
        nx = x1 - (x1 - cx) * (1 - nt)
        ny = base - H * prof(1 - nt, 1.5, 1.35, 0.0)
        cut = ic.mask("ellipse", (nx - 60, ny - 14, nx + 4, ny + 44))
        tint(ic, cut, m, (70, 44, 16), 0.45, 8)
        ic.overlay(lambda d: d.arc((nx - 64, ny - 22, nx + 8, ny + 30), 190, 300, fill=(255, 240, 200, 150), width=4), m)

    def texture(d: ImageDraw.ImageDraw) -> None:
        for _ in range(int((x1 - x0) * H / 140)):
            x, y = R.uniform(x0, x1), R.uniform(top, base)
            r = R.uniform(1.5, 3.5) if not pebbles else R.uniform(4, 11)
            t = R.uniform(-1, 1)
            col = grain + (int(90 * t),) if t > 0 else (50, 34, 16, int(-100 * t))
            if pebbles and R.random() < 0.6:
                d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(R.randint(110, 170),) * 3 + (200,))
                d.arc((x - r, y - r * 0.7, x + r, y + r * 0.7), 200, 340, fill=(230, 226, 214, 170), width=2)
            else:
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        for _ in range(int((x1 - x0) / 40)):  # slip streaks from the crest down the flanks
            sx = R.uniform(x0 + 40, x1 - 40)
            frac = abs(sx - cx) / (x1 - x0)
            sy = top + 16 + frac * H * 1.1
            ln = R.uniform(30, 90)
            slope = -1.3 if sx < cx else 1.3
            d.line([(sx, sy), (sx + slope * ln * 0.45, sy + ln)], fill=(60, 40, 18, 55), width=4)
            d.line([(sx - 5, sy), (sx - 5 + slope * ln * 0.45, sy + ln)], fill=(255, 244, 214, 55), width=3)

    ic.overlay(texture, m)
    tint(ic, ic.mask("rectangle", (x0 - 20, base - 36, x1 + 20, base + 20)), m, (40, 26, 10), 0.3, 16)
    ic.outline(pts, 4, (60, 40, 20, 150))
    # grains that trickled out beyond the foot
    c0 = ImageColor.getrgb(colors[0]) if isinstance(colors[0], str) else colors[0]

    def trickle(d: ImageDraw.ImageDraw) -> None:
        for side in (x0, x1):
            for _ in range(14):
                x = side + R.uniform(-30, 30) + (-10 if side == x0 else 10)
                y = base - R.uniform(0, 12)
                r = R.uniform(2.5, 5) if not pebbles else R.uniform(4, 8)
                d.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8), fill=tuple(int(v * R.uniform(0.7, 1.0)) for v in c0) + (255,))

    ic.overlay(trickle)
    return m


def sluice(ic: Icon, x0: float, x1: float, y: float, h: float) -> None:
    """Low plank sluice box on the ground under the trestles, a thin film of water in it, wet sand."""
    ic.fill(ic.mask("rectangle", (x0, y - 16, x1, y)), "#5a4430", "#3a2a1c", noise=0.2)  # far board
    wm = ic.mask("rectangle", (x0 + 8, y - 12, x1 - 8, y + 6))
    ic.fill(wm, W_LIGHT, W_DEEP, (y - 12, y + 6), noise=0.1)
    flow(ic, wm, x0, x1, y - 10, 0.0, n=int((x1 - x0) / 24))
    planks(ic, [(x0, y + 4), (x1, y + 4), (x1, y + h), (x0, y + h)], "#8a6a46", "#4e3620", board=18, along=(1, 0.0001))
    ic.line([(x0, y + 4), (x1, y + 4)], 7, (176, 138, 96))
    ic.outline([(x0, y - 16), (x1, y - 16), (x1, y + h), (x0, y + h)], 4, (40, 26, 16, 170))
    for x in np.linspace(x0 + 30, x1 - 30, 5):  # riffle cleats
        ic.line([(x, y + 8), (x, y + h - 4)], 8, (66, 46, 28, 200))


def tank(ic: Icon, x0: float, x1: float, y: float, depth: float, face: float) -> None:
    """Plank settling tank from the raised camera: rim in slight perspective (far edge narrower),
    clear water at the far side, the settled sand showing through the shallow near water and
    rising above it where the trough pours in; boarded front."""
    inset, rim = 18, 16
    top = [(x0 + inset, y), (x1 - inset, y), (x1, y + depth), (x0, y + depth)]
    ic.fill(ic.poly_mask(top), "#9a7652", "#5e4430", (y, y + depth), noise=0.2)
    wpts = [(x0 + inset + rim, y + rim * 0.6), (x1 - inset - rim, y + rim * 0.6), (x1 - rim, y + depth - rim * 0.6),
            (x0 + rim, y + depth - rim * 0.6)]
    wm = ic.poly_mask(wpts)
    ic.fill(wm, W_LIGHT, W_DEEP, (y, y + depth), noise=0.08)
    # settled sand on the floor, seen through the clear water nearer the front
    ic.shade(ic.intersect(wm, ic.mask("ellipse", (x0 - 40, y + depth * 0.42, x1 + 40, y + depth * 1.6))), (220, 188, 124), 0.85,
             blur=14)
    # a bar of sand breaking the surface under the inflow
    bar = ic.intersect(wm, ic.mask("ellipse", (x0 + 10, y + depth * 0.5, x0 + 150, y + depth * 1.1)))
    ic.fill(bar, "#e2c486", "#a07a40", (y + depth * 0.5, y + depth), noise=0.2)
    tint(ic, ic.mask("rectangle", (x0, y, x1, y + 24)), wm, (20, 30, 34), 0.45, 6)  # far wall shadow

    def glints(d: ImageDraw.ImageDraw) -> None:
        for _ in range(8):
            gx, gy = ic.random.uniform(x0 + 120, x1 - 60), ic.random.uniform(y + 24, y + depth * 0.5)
            d.line([(gx, gy), (gx + ic.random.uniform(20, 46), gy)], fill=(236, 246, 247, 150), width=4)

    ic.overlay(glints, wm)
    ic.outline(wpts, 3, (40, 26, 16, 130))
    planks(ic, [(x0, y + depth), (x1, y + depth), (x1, y + depth + face), (x0, y + depth + face)], "#94704a", "#553a24",
           board=20, along=(1, 0.0001))
    tint(ic, ic.mask("rectangle", (x1 - 50, y, x1 + 10, y + depth + face)), None, (20, 10, 4), 0.3, 12)
    ic.outline(top[:2] + [(x1, y + depth + face), (x0, y + depth + face)], 4, (40, 26, 16, 180))
    ic.line([(x0, y + depth), (x1, y + depth)], 6, (176, 138, 96))


# ---------------------------------------------------------------- drawing
A, B = (170, 420), (730, 570)  # trough far edge


def trough_y(x: float) -> float:
    return A[1] + (x - A[0]) * (B[1] - A[1]) / (B[0] - A[0])


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86

    # shelter over the drum: posts and a board roof
    for x, top in ((140, 250), (412, 250)):
        timber(ic, (x, top), (x + 4, 690), 26)
    shingles(ic, [(86, 280), (560, 280), (520, 170), (120, 170)], "#8e7658", "#54402c", course=26, stagger=60)
    ic.shade(ic.mask("rectangle", (100, 280, 540, 330)), alpha=0.35, blur=12, clip=True)

    # feed flume from the left bringing the stream onto the drum: thick, plank side, two trestles
    for x in (46, 170):
        timber(ic, (x, 380), (x + 4, 690), 24)
    timber(ic, (30, 388), (190, 392), 18)
    trough(ic, (8, 282), (230, 311), open_w=40, face=62)
    ic.poly([(2, 276), (16, 276), (16, 390), (2, 390)], "#6e5034", "#3e2a1a", edge=4)  # end board

    # low sluice box on the ground under the trestles
    sluice(ic, 110, 730, 612, 66)

    # settling tank at the foot of the trough
    tank(ic, 720, 1010, 548, 96, 58)

    # trestles and the washing trough
    for t in (0.1, 0.48, 0.86):
        x, y = A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t + 96
        timber(ic, (x - 30, y - 6), (x - 44, 690), 20, "#7c5838", "#4a321f")
        timber(ic, (x + 30, y - 6), (x + 44, 690), 20, "#7c5838", "#4a321f")
        timber(ic, (x - 50, y), (x + 50, y + 4), 16, "#7c5838", "#4a321f")
    trough(ic, A, B)
    stream(ic, B[0] - 6, B[1] + 20, 34, 40, 22)  # trough pours into the tank
    # wet dark sand on the sluice boards under the trough outlet
    ic.shade(ic.mask("ellipse", (560, 606, 720, 640)), (70, 50, 24), 0.55, blur=8)

    # drum screen over the head of the trough, fed by the flume
    ic.shade(ic.poly_mask([(200, 450), (480, 525), (480, 560), (200, 485)]), alpha=0.3, blur=12)
    gx, gy = drum(ic, (318, 360), 150, 74)
    sand_rain(ic, 200, 440, lambda x: 360 + (x - 318) * DY / DX + 60, trough_y)

    # heaps in front: small sand heap, the grey gravel heap under the drum, the big clean sand heap
    sand_heap(ic, 6, 336, GROUND - 2, 646, ("#ecc67a", "#8a6230"), peak=0.44)
    gravel_top = 626
    gravel_fall(ic, gx, gy, gravel_top + 20)
    sand_heap(ic, 300, 600, GROUND, gravel_top, ("#a8a298", "#4e4a44"), (240, 236, 226), pebbles=True, peak=0.5)
    sand_heap(ic, 516, 856, GROUND, 566, ("#f4cc80", "#94692e"), peak=0.4, notch=0.34)
    # shovel stuck in the sand beside the cut
    timber(ic, (756, 560), (786, 700), 16, "#9a7650", "#5a4028")
    ic.line([(742, 562), (772, 554)], 12, (106, 80, 54))
    ic.poly([(770, 690), (806, 686), (814, 740), (800, 754), (778, 746)], "#6a6664", "#34302e", edge=4)
    # riddle leaning on the small heap
    ic.fill(ic.mask("ellipse", (150, 640, 280, 812)), "#9a7650", "#5a4028", noise=0.2)
    ic.fill(ic.mask("ellipse", (166, 658, 264, 794)), "#5a4632", "#2e2218", noise=0.1)
    ic.overlay(lambda d: [d.line([(x, 658), (x, 794)], fill=(170, 160, 140, 150), width=3) for x in range(176, 264, 14)]
               + [d.line([(166, y), (264, y)], fill=(170, 160, 140, 150), width=3) for y in range(668, 794, 14)],
               ic.mask("ellipse", (166, 658, 264, 794)))
