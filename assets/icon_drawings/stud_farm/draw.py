"""State Stud (stud_farm): a stately stable range with a clock cupola above a paddock with a bay
stallion and a dappled grey mare.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/stud_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/stud_farm

Identity (upgrade of vanilla horse_breeders, whose icon is a horse head): a whole horse in front of
an ordered stable range built for a state stud: ashlar walls, slate roofs, a pedimented carriage
arch under a clock cupola, arched stable doors along the wings. A pale post-and-rail paddock fence
runs behind the horses; a bay stallion with a blaze stands in front, a grey mare grazes on the left.

Local helpers: ``horse`` (new: whole horse in side view, several coats, standing or grazing),
``stable_door``; ``pasture``, ``post``, ``rail_fence``, ``stones``, ``shingles``, ``planks``,
``hair``, ``tube``, ``smooth``, ``contour`` from cattle_farm, ``crown`` from cattle_rotations.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(*ms: Image.Image) -> Image.Image:
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tone(c, f: float) -> tuple[int, int, int]:
    return tuple(int(min(255, max(0, v * f))) for v in rgb(c))


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def contour(ic: Icon, m: Image.Image, width: int = 7, alpha: float = 0.75, color=(30, 22, 16)) -> None:
    """Soft dark line just inside the edge of ``m`` (separates a form from what is behind it)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(int(width) // 2 * 2 + 1)))
    ic.shade(ring, color, alpha, blur=1)


def tube(path, widths, n: int = 40):
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    L = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / L, dx / L
    a = [(x + nx_ * w / 2, y + ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    b = [(x - nx_ * w / 2, y - ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    return a + b[::-1], a, b


def hair(ic: Icon, mask: Image.Image, box, n: int, length: float = 14, light=(255, 236, 206), dark=(30, 16, 8),
         alpha: int = 60) -> None:
    """Short coat strokes (hair lying back and down) clipped to ``mask``."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            t = rnd.uniform(-1, 1)
            col = light + (int(t * alpha),) if t > 0 else dark + (int(-t * alpha),)
            d.line([(x, y), (x + rnd.uniform(-4, 4), y + length * rnd.uniform(0.6, 1.2))], fill=col, width=3)

    ic.overlay(paint, mask)


# ---------------------------------------------------------------- ground, fences, yard
def pasture(ic: Icon, top_pts, bottom: float, colors=("#86903e", "#4c5420"), tufts: int = 30) -> Image.Image:
    """Grass ground band: uneven top edge, blotchy greens, grass strokes, tufts breaking the edge, earth lip."""
    rnd = ic.random
    pts = [tuple(p) for p in top_pts]
    poly = pts + [(pts[-1][0] - 10, bottom), (pts[0][0] + 10, bottom)]
    m = ic.poly_mask(poly)
    y0 = min(p[1] for p in pts)
    ic.fill(m, colors[0], colors[1], (y0, bottom), noise=0.3, chroma=0.14)
    x0, x1 = pts[0][0], pts[-1][0]
    for _ in range(40):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
        r = rnd.uniform(20, 60)
        col = rnd.choice([(255, 240, 180), (20, 30, 8), (150, 130, 60), (80, 110, 40)])
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y - r * 0.5, x + r * 1.6, y + r * 0.5)), m, col, rnd.uniform(0.08, 0.2),
             10)

    def grass(d):
        for _ in range(int((x1 - x0) * (bottom - y0) / 150)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
            L = rnd.uniform(10, 22) * (0.6 + 0.6 * (y - y0) / max(bottom - y0, 1))
            col = rnd.choice([(170, 176, 90, 110), (60, 80, 24, 130), (120, 140, 56, 110), (200, 190, 110, 80)])
            d.line([(x, y), (x + rnd.uniform(-8, 8), y - L)], fill=col, width=3)

    ic.overlay(grass, m)
    lip = [(p[0], p[1]) for p in [(x0 + 10, bottom - 24), (x1 - 10, bottom - 24), (x1 - 16, bottom + 4),
                                   (x0 + 16, bottom + 4)]]
    ic.fill(ic.poly_mask(lip), "#6a5030", "#3e2c18", noise=0.3)
    tint(ic, ic.mask("rectangle", (0, bottom - 60, SIZE, bottom - 20)), m, (20, 16, 6), 0.3, 12)

    def tuftpaint(d):
        for _ in range(tufts):
            i = rnd.randrange(len(pts) - 1)
            t = rnd.random()
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t + 6
            for _ in range(6):
                d.line([(x, y), (x + rnd.uniform(-10, 10), y - rnd.uniform(12, 26))],
                       fill=rnd.choice([(120, 140, 56, 255), (70, 90, 30, 255), (160, 164, 84, 255)]), width=4)
    ic.overlay(tuftpaint)
    return m


def yard(ic: Icon, top_pts, bottom: float, colors=("#806648", "#443220"), puddles=()) -> Image.Image:
    """Trodden farmyard: churned earth, wet dark and dry light blotches, scattered straw, hoof prints,
    puddles ``(cx, cy, rx)`` with a sky glint, grass tufts along the back edge, earth lip at the front."""
    rnd = ic.random
    pts = [tuple(p) for p in top_pts]
    poly = pts + [(pts[-1][0] - 10, bottom), (pts[0][0] + 10, bottom)]
    m = ic.poly_mask(poly)
    y0 = min(p[1] for p in pts)
    x0, x1 = pts[0][0], pts[-1][0]
    ic.fill(m, colors[0], colors[1], (y0, bottom), noise=0.34, chroma=0.12)
    for _ in range(50):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
        r = rnd.uniform(14, 44)
        col = rnd.choice([(255, 236, 190), (16, 10, 4), (16, 10, 4), (90, 96, 44)])
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y - r * 0.5, x + r * 1.6, y + r * 0.5)), m, col, rnd.uniform(0.1, 0.25), 6)

    def marks(d):
        for _ in range(int((x1 - x0) * (bottom - y0) / 500)):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, bottom)
            if rnd.random() < 0.6:
                a = rnd.uniform(0, math.pi)
                L = rnd.uniform(10, 26)
                d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)],
                       fill=rnd.choice([(214, 180, 104, 190), (170, 134, 70, 170), (236, 210, 140, 150)]), width=3)
            else:
                d.ellipse((x - 7, y - 4, x + 7, y + 4), fill=(20, 12, 6, 120))
                d.arc((x - 7, y - 4, x + 7, y + 4), 180, 330, fill=(220, 190, 140, 80), width=2)

    ic.overlay(marks, m)
    for cx, cy, rx in puddles:
        pm = ic.poly_mask(ic.jitter(cx, cy, rx, rx * 0.28, 12, 0.12))
        ic.fill(pm, "#8a9aa0", "#2e3a3c", (cy - rx * 0.3, cy + rx * 0.3), noise=0.1)
        ic.shade(ic.poly_mask(ic.jitter(cx - rx * 0.2, cy - rx * 0.06, rx * 0.5, rx * 0.06, 8, 0.1)), (230, 236, 236), 0.35)
        ic.outline(ic.jitter(cx, cy, rx, rx * 0.28, 12, 0.02), 3, (40, 30, 20, 120))
    lip = [(x0 + 10, bottom - 24), (x1 - 10, bottom - 24), (x1 - 16, bottom + 4), (x0 + 16, bottom + 4)]
    ic.fill(ic.poly_mask(lip), "#5e4428", "#34261a", noise=0.3)

    def tuftpaint(d):
        for _ in range(18):
            i = rnd.randrange(len(pts) - 1)
            t = rnd.random()
            x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
            y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t + 8
            for _ in range(6):
                d.line([(x, y), (x + rnd.uniform(-10, 10), y - rnd.uniform(10, 22))],
                       fill=rnd.choice([(120, 136, 56, 255), (70, 86, 30, 255), (150, 150, 80, 255)]), width=4)

    ic.overlay(tuftpaint)
    return m


def post(ic: Icon, x: float, base: float, top: float, w: float = 26, wood=((138, 104, 70), (70, 48, 30))) -> None:
    """Split timber post with a weathered top."""
    rnd = ic.random
    pts = [(x - w / 2, base), (x - w / 2 + rnd.uniform(-2, 2), top + 6), (x - w * 0.1, top - rnd.uniform(0, 8)),
           (x + w / 2, top + rnd.uniform(0, 10)), (x + w / 2, base)]
    ic.fill(ic.poly_mask(pts), wood[0], wood[1], (x - w / 2, x + w / 2), vertical=False, noise=0.26)
    ic.line([(x - w * 0.15, top + 16), (x - w * 0.1, base - 10)], 2, (40, 26, 14, 100))
    ic.outline(pts, 4)


def rail_fence(ic: Icon, posts, h: float, rails=(0.3, 0.72), w: float = 24, rail_w: float = 16,
               wood=((150, 116, 80), (78, 54, 34))) -> None:
    """Post-and-rail fence through ``posts`` [(x, base), ...]; rails run between neighbouring posts."""
    rnd = ic.random
    for x, base in posts:
        post(ic, x, base, base - h, w, wood)
    for (xa, ba), (xb, bb) in zip(posts, posts[1:]):
        for fr in rails:
            ya, yb = ba - h * fr + rnd.uniform(-4, 4), bb - h * fr + rnd.uniform(-4, 4)
            ic.line([(xa, ya), (xb, yb)], int(rail_w + 6), (40, 28, 20, 220))
            ic.line([(xa, ya), (xb, yb)], int(rail_w), tone(wood[0], rnd.uniform(0.85, 1.0)))
            ic.line([(xa, ya - rail_w * 0.28), (xb, yb - rail_w * 0.28)], 3, (255, 236, 200, 70))
    for x, base in posts:  # post caps in front of the rails
        ic.line([(x - w * 0.3, base - h * 0.96), (x - w * 0.3, base - h * 0.02)], 3, (255, 236, 200, 50))


def hurdle(ic: Icon, x0: float, x1: float, base: float, h: float, lean: float = 0) -> Image.Image:
    """Woven wattle hurdle: upright stakes with hazel rods woven between them."""
    rnd = ic.random
    pts = [(x0, base), (x0 + lean, base - h), (x1 + lean, base - h + rnd.uniform(-6, 6)), (x1, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#8a6c48", "#4a3420", (base - h, base), noise=0.3, chroma=0.1)

    def weave(d):
        y = base - h + 6
        k = 0
        while y < base:
            for x in np.arange(x0 - 30, x1 + 30, 30):
                off = 15 if k % 2 else 0
                d.arc((x + off, y - 7, x + off + 34, y + 9), 190, 350, fill=(196, 160, 110, 120), width=4)
                d.arc((x + off, y - 5, x + off + 34, y + 11), 10, 170, fill=(40, 26, 12, 150), width=4)
            y += rnd.uniform(12, 16)
            k += 1

    ic.overlay(weave, m)
    for x in np.linspace(x0 + 10, x1 - 10, max(2, int((x1 - x0) / 60))):
        xx = x + rnd.uniform(-5, 5)
        ic.line([(xx, base + 4), (xx + lean, base - h - rnd.uniform(8, 20))], 12, (98, 72, 46))
        ic.line([(xx - 3, base), (xx - 3 + lean, base - h - 6)], 3, (190, 156, 110, 110))
    tint(ic, ic.mask("rectangle", (x0, base - h * 0.4, x1 + 40, base)), m, (20, 12, 4), 0.3, 12)
    ic.outline(pts, 4)
    return m


def muck(ic: Icon, x0: float, x1: float, base: float, top: float, steam: bool = True) -> None:
    """Manure heap: dark rotted mound with fresh straw bedding flecks on top, a wet dark foot, faint steam."""
    rnd = ic.random
    cx = (x0 + x1) / 2
    pts = [(x0 + (x1 - x0) * t + rnd.uniform(-6, 6),
            base - (base - top) * math.sin(math.pi * t) ** 0.7 + rnd.uniform(-8, 8)) for t in np.linspace(0, 1, 18)]
    tint(ic, ic.mask("ellipse", (x0 - 20, base - 20, x1 + 30, base + 22)), None, (10, 6, 2), 0.5, 10)
    m = ic.poly_mask(pts)
    ic.fill(m, "#6a4c30", "#24160c", radial=(x0 + (x1 - x0) * 0.3, top, (x1 - x0) * 0.8), noise=0.35, chroma=0.12)
    for _ in range(26):
        x, y = rnd.uniform(x0, x1), rnd.uniform(top, base)
        r = rnd.uniform(8, 22)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), m,
             rnd.choice([(12, 8, 4), (120, 90, 50), (60, 64, 30)]), 0.3, 3)

    def straw(d):
        for _ in range(int((x1 - x0) * 0.9)):
            x = rnd.uniform(x0, x1)
            yt = np.interp(x, [p[0] for p in pts], [p[1] for p in pts])
            y = rnd.uniform(yt, yt + (base - yt) * 0.55)
            a = rnd.uniform(0, math.pi)
            L = rnd.uniform(10, 24)
            col = rnd.choice([(214, 180, 104, 200), (170, 134, 70, 180), (236, 210, 140, 160)])
            d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (cx, top, x1 + 20, base)), m, (10, 6, 2), 0.3, 24)
    tint(ic, ic.mask("rectangle", (x0 - 10, base - 30, x1 + 10, base + 6)), m, (10, 6, 2), 0.45, 8)
    if steam:
        for k, (dx, h) in enumerate(((-0.15, 110), (0.12, 140))):
            sx = cx + (x1 - x0) * dx
            sy = np.interp(sx, [p[0] for p in pts], [p[1] for p in pts])
            path = [(sx + 14 * math.sin(t * 3 + k) , sy - h * t) for t in np.linspace(0, 1, 8)]
            outline_pts, _, _ = tube(path, [20, 30, 34, 26, 10])
            wisp = ic.poly_mask(outline_pts).filter(ImageFilter.GaussianBlur(8))
            ic.shade(wisp, (236, 230, 220), 0.28, clip=False)


def hay(ic: Icon, pts, strands: int = 220) -> Image.Image:
    """Loose hay: golden mass lit top-left, dark underside, many straw strokes, a few stray stalks."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, "#d0b068", "#6a5026", radial=(min(xs) + (max(xs) - min(xs)) * 0.3, min(ys), (max(ys) - min(ys)) * 1.4),
            noise=0.22)
    rnd = ic.random.uniform

    def straw(d: ImageDraw.ImageDraw) -> None:
        for _ in range(strands):
            x, y = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
            a = rnd(-0.9, 0.9) + (math.pi if ic.random.random() < 0.5 else 0)
            ln = rnd(14, 40)
            t = rnd(-1, 1)
            col = (255, 240, 180, int(t * 110)) if t > 0 else (50, 34, 10, int(-t * 110))
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln * 0.5)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.mask("rectangle", (min(xs), (min(ys) + max(ys)) / 2 + 10, max(xs), max(ys))), m, (30, 16, 4), 0.35, 16)
    for _ in range(10):  # stray stalks sticking out of the silhouette
        i = ic.random.randrange(len(pts))
        x, y = pts[i]
        if y > max(ys) - 20:
            continue
        a = rnd(-2.6, -0.5)
        ic.line([(x, y + 6), (x + math.cos(a) * rnd(14, 26), y + math.sin(a) * rnd(14, 26))], 3, (196, 164, 92))
    return m


# ---------------------------------------------------------------- building materials
def thatch(ic: Icon, ridge, eave, c=("#a88c58", "#5a4626")) -> None:
    """Thatched roof plane seen from above: straw strokes running down the slope, a cut eave."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    rl, rr = np.array(ridge[0], float), np.array(ridge[-1], float)
    el, er = np.array(eave[0], float), np.array(eave[-1], float)
    courses = [0.0, 0.22, 0.41, 0.6, 0.79, 1.0]
    for k in reversed(range(len(courses) - 1)):
        f0, f1 = courses[k], courses[k + 1] + (0.05 if k < len(courses) - 2 else 0)
        n = 26
        low = []
        for j in range(n + 1):
            t = j / n
            p = rl + (rr - rl) * t + ((el + (er - el) * t) - (rl + (rr - rl) * t)) * min(f1, 1.0)
            low.append((p[0] + rnd.uniform(-4, 4), p[1] + (rnd.uniform(-3, 7) if f1 < 1 else 0)))
        up = [tuple(rl + (el - rl) * f0 + np.array([-40, -4])), tuple(rr + (er - rr) * f0 + np.array([40, -4]))]
        band = ic.intersect(ic.poly_mask(up + low[::-1]), m)
        y0 = (rl + (el - rl) * f0)[1]
        y1 = max(p[1] for p in low)
        if f1 < 1:
            ic.shade(ic.intersect(m, ic.poly_mask(low + [(x, y + 22) for x, y in low[::-1]])), (30, 20, 8), 0.45, blur=6)
        tn = rnd.uniform(0.92, 1.06)
        ic.fill(band, tone(c[0], tn), tone(c[1], tn), (y0 - 10, y1 + 30), noise=0.32, chroma=0.14)

        def straw(dr, y0=y0, low=low):
            for _ in range(220):
                j = rnd.uniform(0, n)
                x = np.interp(j, range(n + 1), [p[0] for p in low])
                yb = np.interp(j, range(n + 1), [p[1] for p in low])
                y = rnd.uniform(y0, yb)
                L = rnd.uniform(10, 26)
                col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 80)
                dr.line([(x, y), (x + rnd.uniform(-4, 4), y + L)], fill=col, width=3)

        ic.overlay(straw, band)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 26 + rnd.uniform(-3, 5)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#8a7040", "#4e3c1e", (min(p[1] for p in eave), max(p[1] for p in eave) + 30), noise=0.35)

    def cut(dr):
        for x in np.arange(eave[0][0], eave[-1][0], 7):
            y = np.interp(x, [p[0] for p in eave], [p[1] for p in eave])
            dr.line([(x, y + 2), (x + rnd.uniform(-3, 3), y + 24)], fill=(40, 28, 12, 120), width=2)

    ic.overlay(cut, ic.poly_mask(lip))
    ic.line([tuple(p) for p in ridge], 22, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 8, (150, 128, 84, 170))


def daub(ic: Icon, box, posts=()) -> None:
    """Wattle-and-daub wall: uneven ochre plaster, grime low down, rough posts."""
    rnd = ic.random
    x0, y0, x1, y1 = box
    ic.rect(box, "#b89c6c", "#86704a", noise=0.3, edge=0)
    for _ in range(18):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(10, 26)
        light = rnd.random() < 0.5
        ic.shade(ic.mask("ellipse", (x - r * 1.5, y - r, x + r * 1.5, y + r)), (255, 240, 210) if light else (60, 40, 20),
                 0.14, blur=6)
    ic.shade(ic.mask("rectangle", (x0, y1 - 50, x1, y1)), (50, 44, 20), 0.35, blur=14)
    for x in posts:
        ic.rect((x - 11, y0, x + 11, y1), "#8e6644", "#4e3420", vertical=False, noise=0.25, edge=3)


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, w - 4)
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
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
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone_l = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone_l), ImageDraw.Draw(shadow)
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
    clip.paste(tone_l, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m

def crown(ic: Icon, cx: float, cy: float, r: float, colors=("#6a7e3c", "#22301a"), trunk: bool = True) -> Image.Image:
    """Tree crown built from leaf clumps: lit clumps up left, dark gaps, no outlines; optional trunk."""
    rnd = ic.random
    if trunk:
        ic.poly([(cx - r * 0.1, cy + r * 1.25), (cx - r * 0.06, cy + r * 0.2), (cx + r * 0.08, cy + r * 0.2),
                 (cx + r * 0.14, cy + r * 1.25)], (104, 78, 52), (50, 34, 22), vertical=False, edge=4)
    blobs = [(cx + math.cos(a) * r * d, cy + math.sin(a) * r * d * 0.8, r * rnd.uniform(0.3, 0.46))
             for a, d in ((rnd.uniform(0, 2 * math.pi), rnd.uniform(0.2, 0.62)) for _ in range(16))]
    m = blank()
    for bx, by, br in blobs:
        m = union(m, ic.poly_mask(ic.jitter(bx, by, br, br * 0.85, 12, 0.14)))
    ic.fill(m, colors[0], colors[1], radial=(cx - r * 0.6, cy - r * 0.8, r * 2.2), noise=0.3, chroma=0.12)
    for bx, by, br in sorted(blobs, key=lambda b: b[1]):
        tint(ic, ic.mask("ellipse", (bx - br, by + br * 0.1, bx + br, by + br * 1.1)), m, (10, 16, 4), 0.35, 8)
        tint(ic, ic.mask("ellipse", (bx - br * 0.8, by - br * 0.8, bx + br * 0.3, by)), m, (230, 236, 170), 0.2, 8)

    def leaves(d):
        for _ in range(int(r * 2.2)):
            x, y = rnd.uniform(cx - r, cx + r), rnd.uniform(cy - r, cy + r)
            t = rnd.uniform(-1, 1)
            d.ellipse((x - 6, y - 4, x + 6, y + 4), fill=(220, 230, 150, int(t * 90)) if t > 0 else (10, 20, 4, int(-t * 110)))

    ic.overlay(leaves, m)
    contour(ic, m, 5, 0.5)
    return m


# ---------------------------------------------------------------- horses
HCOATS = {
    # coat (lit, shadow), points (mane, tail, lower legs) (lit, shadow)
    "bay": (("#a8663a", "#3a180a"), ("#2e221c", "#0e0a08")),
    "chestnut": (("#b8743e", "#4a200c"), ("#8a4a26", "#3a1a0a")),
    "grey": (("#dcd8d0", "#6c6860"), ("#8a8680", "#3a3834")),
    "dapple": (("#8e8a84", "#302e2a"), ("#36322e", "#0e0c0a")),
    "black": (("#4a4440", "#100c0a"), ("#2a2624", "#0a0808")),
}
DARK_POINTS = ("bay", "dapple", "black")


def horse(ic: Icon, ox: float, oy: float, s: float = 1.0, left: bool = True, coat: str = "bay", graze: bool = False,
          blaze: bool = True, socks=(), shadow: bool = True) -> Image.Image:
    """Standing horse in side view, near fore hoof at (ox, oy); ``s`` = scale (1 = ~590 px long, ~500 px to
    the ear tips). Head to the left unless ``left`` is False; ``graze`` lowers the neck to the grass.
    Round barrel lit on top with a shaded belly, deep chest, round croup, forelegs with knees, hind legs
    bent at the hock, crested neck. ``socks`` lists white lower legs ("nf", "nh", "ff", "fh"), blended
    into the leg. Returns the mask of the whole animal."""
    rnd = ic.random
    f = 1 if left else -1
    (c1, c2), (p1, p2) = HCOATS[coat]

    def P(pts):
        return [(ox + f * x * s, oy + y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def E(x0, y0, x1, y1):
        return ic.mask("ellipse", box(x0, y0, x1, y1))

    def T(path, widths):
        pts, _, _ = tube(P(path), [w * s for w in widths], n=60)
        return smooth(ic.poly_mask(pts), 3 * s)

    def edges(m, d):
        """(left edge band, right edge band) of a mask, ``d`` px wide."""
        d = max(2, int(d))
        return ImageChops.subtract(m, ImageChops.offset(m, d, 0)), ImageChops.subtract(m, ImageChops.offset(m, -d, 0))

    if shadow:
        tint(ic, ic.mask("ellipse", box(-60, -24, 440, 20)), None, (10, 8, 4), 0.5, 12 * s)

    FORE = ([(56, -270), (52, -196), (50, -136), (47, -82), (44, -34), (34, 0)], [74, 58, 44, 40, 30, 27, 32, 24])
    HIND = ([(316, -290), (344, -214), (376, -150), (360, -92), (350, -38), (334, 0)],
            [120, 92, 62, 42, 31, 28, 32, 24])

    def legpaint(lm, key, k):
        # dark points (or a white sock) fading in below the knee/hock, form from a lit left and dark right edge
        if coat in DARK_POINTS:
            tint(ic, ic.mask("rectangle", (0, oy - 150 * s, SIZE, oy + 4)), lm, tone(p2, k), 0.85, 14 * s)
        if key in socks:
            tint(ic, ic.mask("rectangle", (0, oy - 72 * s, SIZE, oy + 4)), lm, tone((236, 230, 218), k), 0.92, 9 * s)
        le, re = edges(lm, 9 * s)
        below = ic.mask("rectangle", (0, oy - 200 * s, SIZE, oy + 4))
        tint(ic, ic.intersect(le, below), lm, (255, 240, 214), 0.2 * k, 3 * s)
        tint(ic, ic.intersect(re, below), lm, (10, 6, 2), 0.45, 3 * s)
        hoof = ic.intersect(lm, ic.mask("rectangle", (0, oy - 14 * s, SIZE, oy + 4)))
        ic.fill(hoof, tone("#5a4e44", k), "#141010", noise=0.1)

    # far legs first, in shade: fore a little further forward, hind a little back
    ffp = [(x + 42 - (0 if y < -200 else 14 * (1 + y / 200)), y) for x, y in FORE[0]]
    fhp = [(x - 44, y) for x, y in HIND[0]]
    far = blank()
    for path, widths, key in ((ffp, FORE[1], "ff"), (fhp, HIND[1], "fh")):
        lm = T(path, widths)
        ic.fill(lm, tone(c1, 0.6), tone(c2, 0.6), (oy - 280 * s, oy), noise=0.16)
        legpaint(lm, key, 0.6)
        far = union(far, lm)
    contour(ic, far, 4, 0.6)

    # tail from the top of the croup, falling behind the hind leg
    tail, _, _ = tube(P([(392, -372), (430, -340), (446, -264), (440, -170), (424, -90)]),
                      [30 * s, 50 * s, 58 * s, 48 * s, 18 * s])
    tm = smooth(ic.poly_mask(tail), 4 * s)
    ic.fill(tm, p1, p2, radial=(box(386, -360, 446, -100)[0], oy - 360 * s, 260 * s), noise=0.22)
    hair(ic, tm, box(380, -370, 446, -90), int(160 * s), 26 * s, light=(200, 170, 140), alpha=90)
    contour(ic, tm, 4, 0.6)

    # body: withers, dipped back, rounded croup; deep chest, belly line rising to the stifle
    body = [(96, -410), (150, -392), (206, -382), (262, -386), (310, -398), (352, -402), (388, -388), (410, -352),
            (414, -306), (402, -262), (376, -234), (330, -218), (270, -204), (200, -196), (130, -196), (70, -206),
            (28, -228), (-2, -262), (-14, -304), (-4, -344), (30, -380)]
    if graze:
        neck = T([(56, -334), (10, -300), (-30, -256), (-56, -214), (-68, -194)], [170, 128, 96, 72, 60])
        poll, rot = (-66, -196), -35
        crest = [(-70, -208), (-44, -258), (-6, -306), (44, -352), (104, -396)]
    else:
        neck = T([(80, -330), (36, -396), (-10, -456), (-58, -506)], [156, 98, 78, 68])
        poll, rot = (-62, -512), 0
        crest = [(-58, -522), (-24, -506), (20, -474), (66, -434), (106, -404)]
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def H(pts):  # head points relative to the standing poll (-36, -486), rotated when grazing
        hs = 1.0
        return P([(poll[0] + ((x + 36) * cr - (y + 486) * sr) * hs, poll[1] + ((x + 36) * sr + (y + 486) * cr) * hs)
                  for x, y in pts])

    head = [(-24, -500), (-54, -498), (-84, -472), (-118, -432), (-148, -394), (-164, -374), (-160, -352), (-140, -344),
            (-112, -352), (-84, -372), (-54, -396), (-34, -426), (-26, -466)]
    nf, nh = T(*FORE), T(*HIND)
    mass = smooth(union(ic.poly_mask(P(body)), neck, E(300, -404, 414, -236), E(-16, -372, 120, -200)), 6 * s)
    hmask = smooth(ic.poly_mask(H(head)), 5 * s)
    xs = [p[0] for p in P(body + head)]
    lx, top = min(xs), oy - 480 * s
    whole = union(mass, nf, nh)
    ic.fill(whole, c1, c2, radial=(lx + (max(xs) - lx) * 0.3, top, 640 * s), noise=0.16, chroma=0.08)
    # volume: lit top of the barrel, shaded belly, round croup, shoulder and forearm, hindquarter
    tint(ic, E(-30, -276, 430, -140), mass, (16, 8, 4), 0.62, 20 * s)
    tint(ic, E(60, -436, 380, -326), mass, (255, 238, 208), 0.36, 18 * s)
    tint(ic, E(296, -414, 404, -310), mass, (255, 238, 208), 0.22, 14 * s)
    tint(ic, ic.poly_mask(P([(400, -380), (430, -300), (400, -230), (370, -226), (392, -300)])), mass, (10, 6, 2),
         0.35, 12 * s)  # shaded back of the hindquarter
    tint(ic, E(-10, -380, 100, -250), mass, (255, 238, 208), 0.18, 12 * s)  # shoulder
    tint(ic, ic.poly_mask(P([(112, -372), (132, -360), (96, -236), (74, -240)])), mass, (16, 8, 4), 0.18, 22 * s)
    tint(ic, ic.poly_mask(P([(292, -384), (312, -384), (316, -300), (300, -226), (280, -232), (294, -300)])), mass,
         (16, 8, 4), 0.16, 22 * s)
    tint(ic, E(-20, -260, 80, -180), mass, (16, 8, 4), 0.3, 12 * s)  # under the chest
    if graze:
        tint(ic, E(-100, -360, 40, -200), mass, (255, 238, 208), 0.12, 14 * s)
    else:
        tint(ic, E(-90, -520, 30, -350), mass, (255, 238, 208), 0.16, 14 * s)  # lit side of the neck
        tint(ic, ic.poly_mask(P([(-90, -470), (-60, -380), (-16, -300), (-44, -380)])), mass, (16, 8, 4), 0.3, 10 * s)
    if coat == "dapple":
        tint(ic, mass, mass, (26, 24, 22), 0.3)  # iron grey: keep her darker than the pale rails
        dots = blank()
        dd = ImageDraw.Draw(dots)
        for _ in range(70):  # soft pale dapples over the barrel and quarters
            x, y = rnd.uniform(40, 400), rnd.uniform(-396, -260)
            (px, py), = P([(x, y)])
            r = rnd.uniform(9, 16) * s
            dd.ellipse((px - r, py - r * 0.8, px + r, py + r * 0.8), fill=255)
        tint(ic, dots, mass, (226, 222, 212), 0.28, 3 * s)
    hair(ic, mass, box(-60, -500, 420, -200), int(300 * s * s), 6 * s, alpha=22)

    # near legs: thigh and forearm shade into the body, joints, points, socks, hooves
    for lm, key, joint in ((nf, "nf", (50, -136)), (nh, "nh", (376, -150))):
        tint(ic, ic.mask("rectangle", (0, oy - 260 * s, SIZE, oy - 200 * s)), ic.intersect(lm, mass), (16, 8, 4), 0.18,
             10 * s)
        legpaint(lm, key, 1.0)
        jx, jy = P([joint])[0]
        tint(ic, ic.mask("ellipse", (jx - 18 * s, jy - 14 * s, jx + 10 * s, jy + 10 * s)), lm, (255, 240, 214), 0.16,
             4 * s)
    tint(ic, ic.poly_mask(P([(340, -300), (382, -270), (370, -150), (344, -170)])), whole, (10, 6, 2), 0.2, 10 * s)

    # head: finer and smaller, lit forehead, shaded jaw
    hb = H(head)
    ic.fill(hmask, c1, c2, radial=(min(p[0] for p in hb), min(p[1] for p in hb), 200 * s), noise=0.14)
    tint(ic, ic.poly_mask(H([(-44, -434), (-64, -410), (-92, -384), (-70, -380), (-30, -420)])), hmask, (10, 4, 0),
         0.45, 8 * s)
    tint(ic, ic.mask("ellipse", box(-80, -466, -36, -416) if not graze else (0, 0, 1, 1)), hmask, (255, 230, 200), 0.16,
         6 * s)
    if blaze:
        bl = ic.poly_mask(H([(-62, -494), (-54, -490), (-86, -454), (-130, -400), (-150, -378), (-156, -386),
                             (-124, -420), (-90, -466)]))
        ic.fill(ic.intersect(smooth(bl, 3 * s), hmask), "#e4dccc", "#a89c88", noise=0.08)
    muz = ic.intersect(hmask, ic.poly_mask(H(ic.jitter(-146, -366, 26, 22, 10, 0.05))))
    tint(ic, muz, hmask, (40, 26, 20), 0.5, 4 * s)
    if coat == "dapple":
        tint(ic, hmask, hmask, (30, 28, 24), 0.35)
    nx, ny = H([(-152, -378)])[0]
    ic.draw.ellipse((nx - 5 * s, ny - 6 * s, nx + 5 * s, ny + 4 * s), fill=(22, 14, 10, 255))
    ex, ey = H([(-66, -454)])[0]
    ic.draw.ellipse((ex - 8 * s, ey - 6 * s, ex + 8 * s, ey + 6 * s), fill=(16, 10, 8, 255))
    ic.draw.ellipse((ex - 5 * s, ey - 4 * s, ex - 1 * s, ey - 1 * s), fill=(196, 186, 176, 255))
    ic.outline(hb, 3, (40, 20, 10, 150))
    for ear in ([(-40, -494), (-44, -532), (-26, -502)], [(-26, -496), (-22, -536), (-10, -504)]):
        ic.poly(H(ear), tone(c1, 0.9), tone(c2, 0.9), edge=3)

    # mane along the crest and a forelock
    mn, _, _ = tube(P([(x, y + 10) for x, y in crest]), [16 * s, 26 * s, 30 * s, 26 * s, 12 * s])
    mm = smooth(ic.poly_mask(mn), 3 * s)
    ic.fill(mm, p1, p2, noise=0.22)
    hair(ic, mm, box(-80, -500, 110, -180), int(120 * s), 18 * s, light=(200, 170, 140), alpha=90)
    fl = ic.poly_mask(H(ic.jitter(-52, -490, 16, 12, 8, 0.25)))
    ic.fill(fl, p1, p2, noise=0.2)
    contour(ic, whole, max(4, int(6 * s)), 0.55)
    return union(whole, hmask, far, tm)


SEED = 41
REFS = ("horse_breeders", "farming_village", "sheep_farms", "market_village")

WALL = ("#cbbb9c", "#8c7c62")
SLATE = ("#7a7e80", "#3e4244")


def stable_door(ic: Icon, x0: float, x1: float, y0: float, y1: float) -> None:
    """Arched stable door in a dressed stone surround: dark open upper half, shut lower leaf, keystone."""
    w = x1 - x0
    ic.fill(ic.mask("ellipse", (x0 - 14, y0 - 14, x1 + 14, y0 + w + 14)), "#ddd0b4", "#9a8c72", (y0 - 14, y0 + w))
    ic.fill(ic.mask("rectangle", (x0 - 14, y0 + w / 2, x1 + 14, y1)), "#ddd0b4", "#9a8c72", (y0, y1))
    m = union(ic.mask("ellipse", (x0, y0, x1, y0 + w)), ic.mask("rectangle", (x0, y0 + w / 2, x1, y1)))
    ic.fill(m, "#241a12", "#0a0604", noise=0.08)
    mid = y0 + (y1 - y0) * 0.5
    low = ic.intersect(m, ic.mask("rectangle", (x0, mid, x1, y1)))
    planks(ic, (x0, mid, x1, y1), "#7e5a3a", "#4a321e", board=max(12, w / 4), clip=low)
    ic.line([(x0, mid), (x1, mid)], 6, (60, 40, 24))
    ic.overlay(lambda d: d.arc((x0 - 7, y0 - 7, x1 + 7, y0 + w + 7), 180, 360, fill=(60, 50, 40, 200), width=4))
    ic.shade(ic.mask("rectangle", (x0 + w * 0.5 - 7, y0 - 16, x0 + w * 0.5 + 7, y0 + 4)), (60, 50, 40), 0.45)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.86
    ic.grade["gamma"] = 0.72

    GB = 730  # ground line of the stable

    # ---- wings: ashlar walls under hipped slate roofs, arched stable doors, oculi
    ic.shade(ic.mask("ellipse", (40, GB - 40, 980, GB + 40)), alpha=0.4, blur=16, clip=False)
    for x0, x1 in ((80, 300), (460, 940)):
        stones(ic, (x0, 520, x1, GB), WALL[0], WALL[1], course=26, moss=0.03)
    wing = union(ic.mask("rectangle", (80, 520, 300, GB)), ic.mask("rectangle", (460, 520, 940, GB)))
    for x in (130, 222, 520, 616, 712, 808):
        stable_door(ic, x, x + 58, 596, GB)
    for x in (178, 570, 666, 762, 858):
        ic.fill(ic.mask("ellipse", (x, 540, x + 24, 564)), "#241a12", "#0a0604", noise=0.05)
        ic.overlay(lambda d, x=x: d.ellipse((x - 5, 535, x + 29, 569), outline=(220, 208, 184, 255), width=5))
    tint(ic, ic.mask("rectangle", (60, 520, 960, 570)), wing, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (60, GB - 50, 960, GB)), wing, (40, 44, 20), 0.2, 16)
    for x0, x1 in ((80, 300), (460, 940)):
        ic.outline([(x0, 520), (x1, 520), (x1, GB), (x0, GB)], 5)
    shingles(ic, [(50, 534), (320, 534), (300, 400), (110, 400)], SLATE[0], SLATE[1], course=20, stagger=28, edge=6)
    rr = shingles(ic, [(440, 534), (972, 534), (910, 400), (500, 400)], SLATE[0], SLATE[1], course=20, stagger=28,
                  edge=6)
    tint(ic, ic.poly_mask([(760, 390), (990, 390), (990, 540), (800, 540)]), rr, (0, 0, 0), 0.22, 30)
    ic.rect((110, 392, 300, 406), "#5a5e60", "#3a3c3e", edge=4)
    ic.rect((500, 392, 910, 406), "#5a5e60", "#3a3c3e", edge=4)
    for x in (560, 840):  # chimneys
        stones(ic, (x, 330, x + 36, 400), "#b8aa8e", "#7a6c56", course=16, moss=0)
        ic.outline([(x, 330), (x + 36, 330), (x + 36, 400), (x, 400)], 4)
        ic.rect((x - 6, 322, x + 42, 334), "#a89a80", "#6e624e", edge=3)

    # ---- central pavilion: taller, pedimented, carriage arch, clock, cupola
    PX0, PX1, PE = 290, 470, 440
    stones(ic, (PX0, PE, PX1, GB), "#d2c4a6", "#948468", course=26, moss=0.02)
    pav = ic.mask("rectangle", (PX0, PE, PX1, GB))
    for x in (PX0, PX1 - 22):  # quoins
        for k, y in enumerate(range(PE + 20, GB, 32)):
            ic.rect((x - (6 if k % 2 else 0), y, x + 22 + (6 if k % 2 else 0), y + 30), "#e2d6bc", "#a89878", edge=3)
    ax0, ax1 = 330, 430
    ic.fill(ic.mask("ellipse", (ax0 - 18, 560 - 18, ax1 + 18, 660 + 18)), "#e2d6bc", "#a89878", (540, 680))
    ic.fill(ic.mask("rectangle", (ax0 - 18, 610, ax1 + 18, GB)), "#e2d6bc", "#a89878", (600, GB))
    arch = union(ic.mask("ellipse", (ax0, 560, ax1, 660)), ic.mask("rectangle", (ax0, 610, ax1, GB)))
    ic.fill(arch, "#2a1e14", "#0c0806", noise=0.08)
    tint(ic, ic.mask("rectangle", (ax0, GB - 40, ax1, GB)), arch, (120, 100, 70), 0.3, 10)
    ic.overlay(lambda d: d.arc((ax0 - 9, 551, ax1 + 9, 669), 180, 360, fill=(70, 60, 48, 200), width=4))
    ic.fill(ic.mask("ellipse", (362, 470, 398, 506)), "#e8e0cc", "#a89c84", noise=0.05)  # clock face
    ic.overlay(lambda d: d.ellipse((358, 466, 402, 510), outline=(70, 60, 48, 255), width=6))
    ic.line([(380, 488), (380, 474)], 4, (30, 24, 20))
    ic.line([(380, 488), (392, 492)], 4, (30, 24, 20))
    tint(ic, ic.mask("rectangle", (PX0, PE, PX1, PE + 40)), pav, (0, 0, 0), 0.4, 10)
    ic.outline([(PX0, PE), (PX1, PE), (PX1, GB), (PX0, GB)], 5)
    ped = [(PX0 - 20, PE + 6), (PX1 + 20, PE + 6), (380, 336)]
    pm = ic.poly_mask(ped)
    ic.fill(pm, "#d8cab0", "#9a8a70", (336, PE), noise=0.14)
    tint(ic, ic.poly_mask([(380, 336), (PX1 + 20, PE + 6), (380, PE + 6)]), pm, (0, 0, 0), 0.18)
    ic.fill(ic.mask("ellipse", (362, 380, 398, 416)), "#241a12", "#0a0604", noise=0.05)  # oculus
    ic.line([(PX0 - 24, PE + 8), (PX1 + 24, PE + 8)], 14, (190, 176, 150))
    ic.line([(PX0 - 24, PE + 8), (380, 330)], 12, (190, 176, 150))
    ic.line([(380, 330), (PX1 + 24, PE + 8)], 12, (150, 138, 116))
    ic.outline(ped, 5)
    # cupola: square drum with an arched opening, lead cap, finial and vane
    ic.rect((350, 250, 410, 332), "#d8cab0", "#9a8a70", edge=5)
    ic.fill(ic.mask("rectangle", (366, 272, 394, 318)), "#1c140e", "#0a0604", noise=0.05)
    ic.fill(ic.mask("ellipse", (366, 258, 394, 286)), "#1c140e", "#0a0604", noise=0.05)
    tint(ic, ic.mask("rectangle", (390, 250, 410, 332)), None, (0, 0, 0), 0.25, 4)
    cap = [(340, 256), (420, 256), (404, 226), (380, 196), (356, 226)]
    ic.poly(cap, "#7c8484", "#3a4040", edge=5)
    ic.line([(380, 196), (380, 150)], 6, (40, 38, 36))
    ic.fill(ic.poly_mask([(380, 156), (412, 162), (406, 170), (380, 168)]), "#8a7040", "#4a3a1e", noise=0.05)
    ic.fill(ic.mask("ellipse", (374, 178, 386, 190)), "#b89a50", "#6a5020", noise=0.05)

    # ---- paddock ground and the pale rail fence behind the horses
    top = [(0, 770)] + [(x, 750 + rnd.uniform(-8, 8)) for x in np.linspace(60, 960, 14)] + [(1024, 770)]
    pasture(ic, top, 990, colors=("#80903e", "#465220"), tufts=20)
    ic.shade(ic.mask("ellipse", (40, GB - 20, 980, GB + 60)), alpha=0.3, blur=16)
    posts = [(20 + i * 123 + rnd.uniform(-6, 6), 826 + rnd.uniform(-4, 4)) for i in range(9)]
    rail_fence(ic, posts, 116, rails=(0.28, 0.66, 0.95), w=22, rail_w=14, wood=((206, 194, 170), (120, 110, 92)))

    # ---- the horses: a grey mare grazing, the bay stallion in front
    # darker grass and rail shadow behind the mare so she stands off the pale rails
    tint(ic, ic.mask("rectangle", (20, 800, 520, 880)), None, (16, 22, 6), 0.42, 18)
    horse(ic, 318, 904, 0.52, left=False, coat="dapple", graze=True, blaze=False)
    horse(ic, 716, 968, 0.66, left=True, coat="bay", socks=("nf", "fh"))
