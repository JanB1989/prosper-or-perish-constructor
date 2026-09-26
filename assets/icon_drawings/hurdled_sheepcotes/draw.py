"""Hurdled Sheepcotes (hurdled_sheepcotes): a fold of woven wattle hurdles packed with sheep beside a
low thatched cote.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/hurdled_sheepcotes/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/hurdled_sheepcotes

Identity (tier 1 of the sheep chain after vanilla sheep_farms): movable hurdles pitched as a fold on
the common, a flock of cream and grey-white fleeces (two dark faces looking out left and right)
inside, the wattle-and-daub cote with a deep straw roof where the flock is wintered and lambed, a
slatted hay rack against it, an old pollarded willow behind the fold.

Local helpers: ``sheep`` (shared with enclosed_sheep_walks), ``pollard`` (new); ``pasture``, ``yard``, ``post``,
``rail_fence``, ``hurdle``, ``hay``, ``thatch``, ``daub``, ``planks``, ``stones``, ``shingles``,
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
    """Woven wattle hurdle: uneven ragged top, upright sails poking above it, rows of hazel rods woven
    over and under the sails (light where a rod passes over, dark where it dips under), each row jittered."""
    rnd = ic.random
    n_top = max(4, int((x1 - x0) / 22))
    top = [(x0 + (x1 - x0) * t + lean, base - h + rnd.uniform(-8, 8) + 4 * math.sin(t * 5.3 + x0))
           for t in np.linspace(0, 1, n_top)]
    pts = [(x0, base)] + top + [(x1, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#6e5234", "#342414", (base - h, base), noise=0.34, chroma=0.12)
    # sails: thin uprights at irregular spacing, the end ones stouter
    sails = [x0 + 6]
    while sails[-1] < x1 - 40:
        sails.append(sails[-1] + rnd.uniform(26, 48))
    sails.append(x1 - 6)

    def weave(d):
        y = base - h - 4
        k = 0
        while y < base - 4:
            rh = rnd.uniform(10, 15)
            for j, (sa, sb) in enumerate(zip(sails, sails[1:])):
                over = (j + k) % 2 == 0
                g = rnd.uniform(0.8, 1.15)
                col = tuple(int(c * g) for c in ((170, 132, 84) if over else (74, 52, 30))) + (235,)
                ya, yb = y + rnd.uniform(-3, 3), y + rnd.uniform(-3, 3)
                bow = rh * (0.35 if over else -0.2)
                mid = ((sa + sb) / 2 + lean * (1 - (y - base + h) / h), (ya + yb) / 2 - bow)
                la = (sa + lean * (1 - (ya - base + h) / h), ya)
                lb = (sb + lean * (1 - (yb - base + h) / h), yb)
                d.line([la, mid, lb], fill=col, width=int(rh * 0.8), joint="curve")
                if over:
                    d.line([(la[0], la[1] - rh * 0.25), (mid[0], mid[1] - rh * 0.25), (lb[0], lb[1] - rh * 0.25)],
                           fill=(226, 196, 140, 110), width=3)
                else:
                    d.line([(la[0], la[1] + rh * 0.35), (mid[0], mid[1] + rh * 0.35), (lb[0], lb[1] + rh * 0.35)],
                           fill=(20, 12, 6, 150), width=3)
            y += rh
            k += 1

    ic.overlay(weave, m)
    for i, x in enumerate(sails):
        stout = i in (0, len(sails) - 1)
        xx = x + rnd.uniform(-3, 3)
        tip = base - h - rnd.uniform(2, 16) - (8 if stout else 0)
        w = 13 if stout else 7
        ic.line([(xx, base + (8 if stout else 0)), (xx + lean, tip)], w + 4, (34, 22, 12, 200))
        ic.line([(xx, base + (6 if stout else 0)), (xx + lean, tip + 2)], w, (104, 78, 50))
        ic.line([(xx - w * 0.25, base), (xx - w * 0.25 + lean, tip + 4)], 2, (200, 168, 118, 130))
    tint(ic, ic.mask("rectangle", (x0 - 10, base - h * 0.45, x1 + 40, base)), m, (20, 12, 4), 0.35, 12)
    ic.outline(pts, 4, (30, 20, 12, 200))
    return m


def pollard(ic: Icon, cx: float, base: float, top: float, r: float,
            colors=("#62763a", "#162010")) -> Image.Image:
    """Pollarded willow: short thick trunk with a swollen knuckle at the cut, one head of shoots
    massed in a few large clumps (each lit top-left, shaded underneath, dark gap to the next)."""
    rnd = ic.random
    kx, ky = cx + 6, top  # knuckle centre
    tint(ic, ic.mask("ellipse", (cx - 80, base - 16, cx + 90, base + 16)), None, (10, 8, 4), 0.45, 10)
    trunk = [(cx - 44, base + 6), (cx - 34, base - 60), (cx - 30, ky + 30), (kx - 50, ky + 4), (kx + 48, ky + 2),
             (cx + 34, ky + 34), (cx + 38, base - 50), (cx + 52, base + 6)]
    tm = smooth(ic.poly_mask(trunk), 6)
    ic.fill(tm, (132, 104, 72), (46, 32, 20), (cx - 50, cx + 50), vertical=False, noise=0.32, chroma=0.1)
    knuckle = ic.poly_mask(ic.jitter(kx, ky + 6, 54, 42, 12, 0.14))
    ic.fill(knuckle, (140, 112, 78), (52, 36, 22), radial=(kx - 30, ky - 20, 100), noise=0.3)

    def bark(d):
        for _ in range(26):
            x = rnd.uniform(cx - 34, cx + 36)
            y = rnd.uniform(ky + 10, base - 10)
            d.line([(x, y), (x + rnd.uniform(-3, 3), y + rnd.uniform(18, 50))],
                   fill=(30, 20, 10, 120) if rnd.random() < 0.6 else (210, 180, 130, 70), width=3)

    ic.overlay(bark, union(tm, knuckle))
    tint(ic, ic.mask("ellipse", (kx - 90, ky + 10, kx + 60, ky + 80)), union(tm, knuckle), (10, 6, 2), 0.35, 10)
    contour(ic, union(tm, knuckle), 5, 0.55)
    # shoots springing from the knuckle, visible between the clumps
    for a in (-2.4, -1.9, -1.5, -1.1, -0.7):
        ic.line([(kx + math.cos(a) * 30, ky - 6), (kx + math.cos(a) * r * 0.9, ky + math.sin(a) * r * 0.9)], 5,
                (84, 68, 44))
    # clumps back to front: the rear top clump first, then left and right, the front clump last
    clumps = [(kx + r * 0.08, ky - r * 0.9, r * 0.6), (kx - r * 0.55, ky - r * 0.55, r * 0.56),
              (kx + r * 0.6, ky - r * 0.5, r * 0.54), (kx - r * 0.05, ky - r * 0.34, r * 0.48)]
    head = blank()
    for bx, by, br in clumps:
        cm = blank()
        for _ in range(6):
            a, d = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.1, 0.5)
            sx, sy = bx + math.cos(a) * br * d, by + math.sin(a) * br * d * 0.7
            sr = br * rnd.uniform(0.62, 0.82)
            cm = union(cm, ic.poly_mask(ic.jitter(sx, sy, sr, sr * 0.8, 16, 0.16)))
        cm = smooth(cm, 3)
        # cast shadow of this clump on what lies behind it
        tint(ic, cm.filter(ImageFilter.MaxFilter(15)), head, (8, 12, 4), 0.45, 6)
        ic.fill(cm, colors[0], colors[1], radial=(bx - br * 0.6, by - br * 0.8, br * 2.1), noise=0.3, chroma=0.12)
        tint(ic, ic.mask("ellipse", (bx - br * 1.1, by + br * 0.05, bx + br * 1.2, by + br * 1.2)), cm, (8, 14, 4), 0.45,
             10)
        tint(ic, ic.mask("ellipse", (bx - br * 0.85, by - br * 0.85, bx + br * 0.2, by - br * 0.1)), cm,
             (226, 234, 160), 0.28, 10)

        def sprigs(d, bx=bx, by=by, br=br):  # a few leafy strokes along the lit rim, no speckle
            for _ in range(14):
                a = rnd.uniform(math.pi * 1.0, math.pi * 1.6)
                x, y = bx + math.cos(a) * br * 0.75, by + math.sin(a) * br * 0.6
                d.line([(x, y), (x + rnd.uniform(-10, 4), y - rnd.uniform(6, 16))], fill=(200, 212, 140, 90), width=4)

        ic.overlay(sprigs, cm)
        contour(ic, cm, 5, 0.55, (14, 20, 8))
        head = union(head, cm)
    return union(head, tm, knuckle)


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


# ---------------------------------------------------------------- sheep (shared by the two sheep tiers)
FACES = {
    # face and legs (lit, shadow)
    "dark": (("#4e423a", "#16100c"), ("#3e342e", "#120e0c")),
    "light": (("#dcd0b8", "#7e705c"), ("#c0b49c", "#6a5e4c")),
    "brown": (("#8a6446", "#34221a"), ("#6e5240", "#2a1e16")),
}


def sheep(ic: Icon, ox: float, oy: float, s: float = 1.0, left: bool = True, face: str = "light", graze: bool = False,
          fleece=("#ece4d0", "#8c8270"), shadow: bool = True, head: bool = True, gap: bool = False) -> Image.Image:
    """Woolly sheep in side view, near fore hoof at (ox, oy); ``s`` = scale (1 = ~400 px long).

    Head to the left unless ``left`` is False; ``graze`` lowers the head to the grass. The fleece is a
    bumpy cloud with curl texture, lit upper left, a core shadow along the belly. Returns the mask.
    """
    rnd = ic.random
    f = 1 if left else -1
    (fc1, fc2), (lc1, lc2) = FACES[face]

    def P(pts):
        return [(ox + f * x * s, oy + y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    if shadow:
        tint(ic, ic.mask("ellipse", box(-40, -22, 330, 18)), None, (10, 8, 4), 0.5, 10 * s)
    if gap:  # dark cast shadow on whatever stands behind, so neighbouring fleeces separate
        tint(ic, ic.mask("ellipse", box(-30, -290, 340, -40)), None, (16, 12, 6), 0.55, 12 * s)

    # legs: far pair in shade behind, near pair in front of the belly
    def leg(x, w=22):
        return [(x, -120), (x + w, -120), (x + w - 3, -40), (x + w - 1, -14), (x + w + 2, 0), (x - 2, 0), (x + 1, -14),
                (x + 3, -40)]

    far = union(ic.poly_mask(P(leg(70, 20))), ic.poly_mask(P(leg(222, 20))))
    ic.fill(far, tone(lc1, 0.6), tone(lc2, 0.6), (oy - 120 * s, oy), noise=0.16)
    contour(ic, far, 4, 0.5)
    near = union(ic.poly_mask(P(leg(34))), ic.poly_mask(P(leg(252))))
    ic.fill(near, lc1, lc2, (oy - 120 * s, oy), noise=0.16)
    for x in (34, 252):
        tint(ic, ic.mask("rectangle", box(x, -120, x + 7, -20)), near, (255, 240, 214), 0.16, 2)
        tint(ic, ic.intersect(ic.poly_mask(P(leg(x))), ic.mask("rectangle", box(x - 4, -16, x + 28, 2))), near,
             (10, 6, 4), 0.55)
    contour(ic, near, 4, 0.55)

    # fleece: body ellipse plus a ring of bumps along the top and ends
    cx, cy, rx, ry = 150, -170, 158, 86
    m = ic.mask("ellipse", box(cx - rx, cy - ry, cx + rx, cy + ry))
    for k in range(22):
        a = math.pi * (0.92 + 1.16 * k / 21) + rnd.uniform(-0.05, 0.05)
        bx, by = cx + math.cos(a) * rx * 0.9, cy + math.sin(a) * ry * 0.9
        br = rnd.uniform(26, 36)
        m = union(m, ic.poly_mask(P(ic.jitter(bx, by, br, br * 0.85, 10, 0.12))))
    for k in range(7):  # ragged belly wool
        bx = cx - rx * 0.7 + k * rx * 0.24
        m = union(m, ic.poly_mask(P(ic.jitter(bx, cy + ry * 0.8, 22, 18, 9, 0.2))))
    m = smooth(m, 3 * s)
    xs = [p[0] for p in P([(cx - rx, 0), (cx + rx, 0)])]
    ic.fill(m, fleece[0], fleece[1], radial=(min(xs) + (max(xs) - min(xs)) * 0.3, oy + (cy - ry) * s, 380 * s),
            noise=0.22, chroma=0.06)
    tint(ic, ic.mask("ellipse", box(cx - rx * 1.1, cy + ry * 0.05, cx + rx * 1.1, cy + ry * 1.4)), m, (34, 26, 16),
         0.58, 16 * s)
    tint(ic, ic.mask("ellipse", box(cx - rx * 0.8, cy - ry * 1.2, cx + rx * 0.6, cy - ry * 0.3)), m, (255, 250, 236),
         0.28, 14 * s)

    def curls(d):
        n = int(260 * s * s) + 30
        bx0, by0, bx1, by1 = box(cx - rx - 30, cy - ry - 30, cx + rx + 30, cy + ry + 20)
        for _ in range(n):
            x, y = rnd.uniform(bx0, bx1), rnd.uniform(by0, by1)
            r = rnd.uniform(7, 13) * max(s, 0.45)
            d.arc((x - r, y - r * 0.8, x + r, y + r * 0.8), 190, 330, fill=(255, 252, 240, int(rnd.uniform(60, 130))),
                  width=max(2, int(4 * s)))
            d.arc((x - r, y - r * 0.8 + 2, x + r, y + r * 0.8 + 2), 10, 170, fill=(70, 58, 42, int(rnd.uniform(60, 120))),
                  width=max(2, int(4 * s)))

    ic.overlay(curls, m)
    contour(ic, m, max(4, int(6 * s)), 0.6, (50, 40, 28))

    # head: local points around the poll, rotated down when grazing
    if head:
        poll, rot = ((-6, -150), -58) if graze else ((-8, -236), 0)
        cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))

        def H(pts):
            return P([(poll[0] + x * cr - y * sr, poll[1] + x * sr + y * cr) for x, y in pts])

        hd = [(14, -10), (-24, -14), (-56, 6), (-84, 36), (-96, 58), (-88, 72), (-62, 76), (-34, 64), (-6, 46), (18, 26)]
        hm = smooth(ic.poly_mask(H(hd)), 4 * s)
        hb = H(hd)
        ic.fill(hm, fc1, fc2, radial=(min(p[0] for p in hb), min(p[1] for p in hb), 150 * s), noise=0.16)
        tint(ic, ic.poly_mask(H([(-6, 46), (-34, 64), (-62, 76), (-40, 90), (20, 60)])), hm, (10, 6, 4), 0.35, 6 * s)
        tint(ic, ic.poly_mask(H([(-24, -12), (-56, 6), (-72, 24), (-50, 22), (-20, 4)])), hm, (255, 240, 214), 0.22,
             5 * s)
        # ear sticking out sideways and back
        ear = [(4, 4), (30, -8), (54, -2), (46, 12), (20, 16)]
        em = ic.poly_mask(H(ear))
        ic.fill(em, tone(fc1, 0.95), tone(fc2, 0.9), noise=0.14)
        tint(ic, ic.poly_mask(H([(12, 8), (32, -2), (46, 4), (28, 10)])), em, (150, 96, 84), 0.3, 2)
        ic.outline(H(ear), 3, (30, 20, 14, 170))
        ex, ey = H([(-40, 18)])[0]
        rr = max(3, 6 * s)
        ic.draw.ellipse((ex - rr, ey - rr * 0.8, ex + rr, ey + rr * 0.8), fill=(14, 10, 8, 255))
        nx, ny = H([(-86, 58)])[0]
        ic.draw.ellipse((nx - rr * 0.8, ny - rr * 0.6, nx + rr * 0.8, ny + rr * 0.6), fill=(20, 14, 12, 255))
        ic.outline(hb, 3, (30, 20, 14, 160))
        # wool poll cap over the forehead
        cap = ic.poly_mask(H(ic.jitter(6, 2, 28, 20, 9, 0.2)))
        ic.fill(cap, fleece[0], fleece[1], radial=(hb[0][0] - 20 * s, hb[0][1] - 20 * s, 60 * s), noise=0.2)
        tint(ic, cap, cap, (60, 50, 36), 0.2)
        m = union(m, hm)
    return union(m, near, far)


SEED = 17
REFS = ("sheep_farms", "farming_village", "fulani_cattle_rearing_pen", "free_village")


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.84
    ic.grade["gamma"] = 0.72


    # ---- an old pollarded willow behind the fold
    pollard(ic, 250, 740, 566, 150)

    # ---- the cote: low wattle-and-daub house under a deep straw roof, back right
    CX0, CX1, CE, CB = 560, 990, 500, 760
    ic.shade(ic.mask("ellipse", (520, 720, 1020, 800)), alpha=0.4, blur=16, clip=False)
    daub(ic, (CX0, CE, CX1, CB), posts=(CX0 + 6, 700, 850, CX1 - 6))
    dx0, dx1, dy0 = 730, 832, 590
    ic.rect((dx0, dy0, dx1, CB), "#140e08", "#050302", noise=0.08, edge=0)
    ic.beam((dx0 - 12, dy0 - 4), (dx1 + 12, dy0 - 4), 18, (108, 78, 50))
    ic.window(910, 560, 950, 596)
    ic.shade(ic.mask("rectangle", (CX0, CE, CX1, CE + 60)), alpha=0.5, blur=12)
    ridge = [(650, 290), (780, 282), (910, 292)]
    eave = [(x, 520 + rnd.uniform(-6, 8)) for x in np.linspace(520, 1020, 20)]
    thatch(ic, ridge, eave, c=("#b09460", "#5e4828"))
    ic.shade(ic.poly_mask([(840, 270), (1030, 270), (1030, 560), (880, 560)]), alpha=0.22, blur=40)

    # ---- ground: the common, trodden and strawed inside the fold
    top = [(6, 736)] + [(x, 716 + rnd.uniform(-10, 10)) for x in np.linspace(70, 950, 14)] + [(1018, 736)]
    pasture(ic, top, 968, colors=("#7c8640", "#465020"))
    fold = ic.poly_mask([(40, 752), (680, 752), (710, 950), (20, 950)])
    tint(ic, fold, None, (120, 96, 56), 0.35, 20)
    ic.shade(ic.mask("ellipse", (520, 700, 1020, 790)), alpha=0.3, blur=18)

    # ---- a hay rack against the cote: dark slatted crib over the hay
    hay(ic, [(846, 800), (846, 744), (872, 716), (930, 708), (986, 724), (1000, 760), (1000, 800)], strands=160)
    tint(ic, ic.mask("rectangle", (846, 690, 1004, 800)), None, (20, 12, 4), 0.25, 8)
    for x in np.arange(862, 1000, 22):
        xx = x + rnd.uniform(-2, 2)
        ic.line([(xx, 700), (xx + 6, 800)], 10, (34, 22, 12))
        ic.line([(xx, 700), (xx + 6, 800)], 6, (84, 60, 38))
        ic.line([(xx - 2, 702), (xx + 4, 796)], 2, (180, 146, 100, 120))
    ic.line([(840, 800), (1008, 798)], 14, (34, 22, 12))
    ic.line([(840, 800), (1008, 798)], 8, (104, 76, 48))
    for x in (846, 1000):
        post(ic, x, 816, 690, 18)
    ic.line([(836, 700), (1012, 694)], 14, (40, 28, 20))
    ic.line([(836, 700), (1012, 694)], 9, (132, 100, 66))

    # ---- back hurdles of the fold, a spare one leaned against the cote
    xs = [30, 196, 360, 520, 676]
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        hurdle(ic, a, b + 6, 772 + i * 2, 124 + rnd.uniform(-8, 8), lean=rnd.uniform(-5, 5))
    hurdle(ic, 700, 800, 806, 160, lean=24)

    # ---- the flock: two behind, two in front with dark faces looking out left and right
    cream, greywhite = ("#eee0c0", "#86765a"), ("#dad9d2", "#6e6e68")
    sheep(ic, 262, 840, 0.52, left=True, face="light", graze=True, fleece=greywhite)
    sheep(ic, 580, 834, 0.5, left=False, face="light", fleece=cream, gap=True)
    sheep(ic, 96, 920, 0.68, left=True, face="dark", fleece=cream, gap=True)
    sheep(ic, 660, 926, 0.7, left=False, face="dark", fleece=greywhite, gap=True)

    # ---- front hurdles, low, closing the fold
    xs = [14, 190, 364, 540, 716]
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        hurdle(ic, a, b + 6, 972 - i * 2, 60 + rnd.uniform(-5, 5), lean=rnd.uniform(-4, 4))
