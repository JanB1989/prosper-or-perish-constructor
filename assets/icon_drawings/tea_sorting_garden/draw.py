"""Tea Sorting Garden: tea rows on the hill behind a tiled sorting pavilion with racks of round trays.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/tea_sorting_garden/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tea_sorting_garden

Identity: the tier above the Tea Garden. The same ribbed hill of clipped tea bushes now sits behind
an open pavilion with a grey tiled roof and upswept eaves, whose racks hold round bamboo trays of
withering and rolled leaf; in front, big trays of fresh green and dark rolled tea and a tea chest
topped with paper-wrapped packets.

Local helpers: ``hedge``, ``leaves``, ``leafpile`` (as in tea_garden), ``tray`` (round bamboo tray
with fresh or rolled leaf), ``rolled`` (twisted fired tea grains), ``tileroof`` (round-tile roof
plane with channels down the slope and upswept corners), ``packet`` (paper-wrapped tea block).
"""

import math

import numpy as np
from PIL import Image, ImageChops

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 43
REFS = ("terraces", "porcelain_guild", "farming_village", "tobacco_plantation")

BUSH = ("#78aa64", "#0e2416")
FLUSH = [(172, 200, 84), (156, 190, 72), (186, 206, 96), (140, 176, 66)]
EARTH = ("#8c603c", "#4e3420")


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def leaf_pts(x, y, L, ang, w=0.42):
    """Small pointed leaf (lens) as polygon points."""
    a = math.radians(ang)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array([x, y]) - d * L / 2
    ts = np.linspace(0, 1, 7)
    s1 = [b + d * L * t + n * L * w / 2 * math.sin(math.pi * t) for t in ts]
    s2 = [b + d * L * t - n * L * w / 2 * math.sin(math.pi * t) for t in ts]
    return [tuple(p) for p in s1 + s2[::-1]]


def leaves(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Paint many small leaves (x, y, length, angle, rgba) in one blended layer."""

    def paint(dr):
        for x, y, L, ang, col in items:
            dr.polygon(leaf_pts(x, y, L, ang), fill=col)

    ic.overlay(paint, clip)


def hedge(ic: Icon, base, h: float, step: float = 0.95) -> Image.Image:
    """Row of clipped tea bushes along the baseline ``base`` (list of points, left to right).

    Rounded domes that touch at their shoulders, shaped by a few large soft leaf-mass tones (lit
    upper left, core shadow lower right), sparse leaf dabs, a thin broken edge of yellow-green new
    shoots on the crown and a dark underside. Returns the row mask."""
    rnd = ic.random
    xs = np.array([p[0] for p in base])
    ys = np.array([p[1] for p in base])
    domes = []
    x = xs[0] + h * 0.45
    while x < xs[-1] - h * 0.35:
        y = float(np.interp(x, xs, ys))
        rx = h * rnd.uniform(0.52, 0.64)
        ry = h * rnd.uniform(0.44, 0.56)
        domes.append((x, y - ry * 0.92, rx, ry))
        x += h * step * rnd.uniform(0.86, 1.12)
    m = blank()
    # a low band under the domes keeps the row continuous; notches between domes stay visible
    band = [(xs[0] + h * 0.3, ys[0])] + [(x, y - h * 0.32) for x, y in zip(xs, ys)][3:-3]
    band += [(xs[-1] - h * 0.3, ys[-1])] + [(x, y) for x, y in zip(xs[::-1], ys[::-1])]
    m = union(m, ic.poly_mask(band))
    for cx, cy, rx, ry in domes:
        m = union(m, ic.poly_mask(ic.jitter(cx, cy, rx, ry, 22, 0.04)))
    top = min(ys) - h * 1.1
    ic.fill(m, BUSH[0], BUSH[1], (top, max(ys)), noise=0.3, chroma=0.12)
    for cx, cy, rx, ry in domes:  # soft leaf masses: lit upper left, core shadow lower right
        ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - rx * 0.95, cy - ry * 1.0, cx + rx * 0.35, cy + ry * 0.05))),
                 (150, 190, 120), 0.30, blur=h * 0.16)
        ic.shade(ic.intersect(m, ic.mask("ellipse", (cx + rx * 0.05, cy - ry * 0.2, cx + rx * 1.35, cy + ry * 1.3))),
                 (4, 12, 8), 0.46, blur=h * 0.14)
        for _ in range(3):  # a few big clumps of foliage within the bush
            a, r = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.2, 0.6)
            bx, by = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
            ic.shade(ic.intersect(m, ic.mask("ellipse", (bx - rx * 0.4, by - ry * 0.3, bx + rx * 0.4, by + ry * 0.3))),
                     (120, 160, 100) if by < cy else (6, 16, 10), 0.18, blur=h * 0.1)
    items = []
    for cx, cy, rx, ry in domes:
        for _ in range(int(22 * h / 100)):
            a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.6
            x, y = cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r
            v = (y - (cy - ry)) / (2 * ry)
            L = h * rnd.uniform(0.11, 0.16)
            col = (110, 150, 96, 60) if rnd.random() < 0.45 - 0.6 * v else (8, 22, 12, 80)
            items.append((x, y, L, rnd.uniform(0, 180), col))
    leaves(ic, items, m)
    flush = []
    for cx, cy, rx, ry in domes:  # thin broken edge of new shoots along the crown
        u = -0.85
        while u < 0.6:
            if rnd.random() < 0.6:
                x = cx + u * rx
                y = cy - ry * math.sqrt(max(0.0, 1 - u * u)) * 0.96 + h * 0.03
                c = rnd.choice(FLUSH)
                a = 220 if u < 0.1 else 140
                flush.append((x, y, h * rnd.uniform(0.07, 0.1), rnd.uniform(-20, 20) + 70 * u, c + (a,)))
            u += rnd.uniform(0.06, 0.14)
    leaves(ic, flush, m)
    ic.shade(ic.intersect(m, ic.poly_mask([(x, y - h * 0.34) for x, y in base] + [(x, y + 5) for x, y in base[::-1]])),
             (4, 10, 6), 0.55, blur=h * 0.1)
    return m


def leafpile(ic: Icon, mask: Image.Image, cx: float, top: float, bottom: float, w: float) -> None:
    """Heap of fresh leaf: bright yellow-green body, lit crown, many small leaf dabs and pale tips."""
    rnd = ic.random
    ic.fill(mask, "#a4c056", "#2c4a16", radial=(cx - w * 0.3, top, w * 0.95), noise=0.3)
    items = []
    for _ in range(int(w * 1.4)):
        x, y = rnd.uniform(cx - w / 2, cx + w / 2), rnd.uniform(top, bottom)
        v = (y - top) / max(bottom - top, 1)
        col = rnd.choice(((168, 196, 88, 220), (132, 170, 70, 210), (84, 124, 42, 210), (208, 220, 120, 210)))
        if rnd.random() < v * 0.5:
            col = (26, 44, 14, 190)
        items.append((x, y, rnd.uniform(14, 24), rnd.uniform(0, 180), col))
    leaves(ic, items, mask)


def backbasket(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Tall wicker back-basket flaring to the mouth, with woven bands and a rolled rim."""
    w = x1 - x0
    body = [(x0, y0), (x1, y0), (x1 - w * 0.16, y1 - 12), (x1 - w * 0.24, y1), (x0 + w * 0.24, y1),
            (x0 + w * 0.16, y1 - 12)]
    m = ic.poly_mask(body)
    ic.fill(m, "#a47a46", "#40280f", (x0, x1), vertical=False, noise=0.28)
    rnd = ic.random

    def weave(dr):
        for k, y in enumerate(np.arange(y0 + 14, y1, 13)):
            dr.line([(x0, y), (x1, y + rnd.uniform(-2, 2))], fill=(70, 46, 22, 150), width=3)
            off = 0 if k % 2 else 9
            for x in np.arange(x0 + off, x1, 18):
                dr.line([(x, y - 11), (x + 2, y)], fill=(230, 200, 140, 70), width=4)
        for x in np.arange(x0 + 20, x1, 26):
            dr.line([(x, y0), (x + (x0 + w / 2 - x) * 0.3, y1)], fill=(60, 40, 20, 90), width=3)

    ic.overlay(weave, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0 + w * 0.55, 0, SIZE, SIZE))), (20, 12, 4), 0.35, blur=14)
    ic.outline(body, 5, (34, 20, 10, 220))
    ic.line([(x0 - 4, y0 + 2), (x1 + 4, y0 + 2)], 18, (92, 62, 32))
    ic.line([(x0 - 2, y0 - 2), (x1 + 2, y0 - 2)], 6, (186, 150, 96, 200))
    # carrying strap looping over the rim
    ic.line([(x0 + w * 0.22, y0 + 4), (x0 + w * 0.12, y0 + (y1 - y0) * 0.55), (x0 + w * 0.3, y1 - 30)], 12, (70, 46, 26))


def rolled(ic: Icon, clip: Image.Image, x0: float, x1: float, y0: float, y1: float, size: float) -> None:
    """Rolled, fired tea: small twisted dark grains in olive, black-green and brown."""
    rnd = ic.random
    cols = ((52, 60, 24), (30, 38, 16), (70, 60, 28), (46, 34, 18), (80, 84, 34))

    def paint(dr):
        y = y0
        while y < y1:
            x = x0 + rnd.uniform(0, size)
            while x < x1:
                c = rnd.choice(cols)
                L = size * rnd.uniform(0.9, 1.5)
                a = math.radians(rnd.uniform(0, 180))
                dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2 * 0.6
                dr.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(20, 16, 8, 200), width=int(size * 0.7) + 2)
                dr.line([(x - dx, y - dy - 1), (x + dx, y + dy - 1)], fill=c + (255,), width=int(size * 0.55))
                if rnd.random() < 0.3:  # glint on a curled edge
                    dr.line([(x - dx * 0.5, y - dy * 0.5 - 2), (x + dx * 0.2, y + dy * 0.2 - 2)], fill=(170, 160, 100, 140), width=2)
                x += size * rnd.uniform(0.8, 1.2)
            y += size * 0.5

    ic.overlay(paint, clip)


def tray(ic: Icon, cx: float, cy: float, rx: float, ry: float, content: str, rim: float = 12) -> None:
    """Round bamboo tray seen from the raised camera: woven rim, leaf ('fresh' or 'rolled') inside."""
    ic.shade(ic.mask("ellipse", (cx - rx * 1.02, cy - ry * 0.6, cx + rx * 1.08, cy + ry * 1.5)), alpha=0.45,
             blur=max(rim * 0.8, 4), clip=True)
    outer = ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    ic.fill(outer, "#b89262", "#5e4226", radial=(cx - rx * 0.6, cy - ry, rx * 2.0), noise=0.25)
    # the tray's side wall, visible below its front rim
    wall = ic.intersect(ic.mask("ellipse", (cx - rx, cy - ry + rim * 0.9, cx + rx, cy + ry + rim * 0.9)),
                        ic.mask("rectangle", (0, cy, SIZE, SIZE)))
    ic.fill(wall, "#8a6a40", "#4a3218", (cx - rx, cx + rx), vertical=False, noise=0.25)
    ic.fill(outer, "#b89262", "#5e4226", radial=(cx - rx * 0.6, cy - ry, rx * 2.0), noise=0.25)
    inner = ic.mask("ellipse", (cx - rx + rim, cy - ry + rim * 0.6, cx + rx - rim, cy + ry - rim * 0.5))
    if content == "rolled":
        ic.fill(inner, "#34381a", "#12160a", (cy - ry, cy + ry), noise=0.3)
        rolled(ic, inner, cx - rx, cx + rx, cy - ry, cy + ry, max(rx * 0.07, 6))
    else:
        leafpile(ic, inner, cx, cy - ry, cy + ry, rx * 2)
    ic.shade(ic.intersect(inner, ic.mask("rectangle", (0, cy - ry, SIZE, cy - ry + rim * 1.6))), alpha=0.4, blur=4)
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(44, 28, 14, 210), width=4))
    ic.overlay(lambda d: d.arc((cx - rx + 3, cy - ry + 2, cx + rx - 3, cy + ry - 2), 190, 300,
                               fill=(240, 200, 124, 210), width=max(3, int(rim * 0.35))))


def tileroof(ic: Icon, ridge, eave) -> Image.Image:
    """East Asian tiled roof plane: rows of round-tile channels running down the slope, upswept
    eave corners, a heavy ridge. Returns the roof mask."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, "#7c7872", "#3a3634", (min(ys), max(ys)), noise=0.22, chroma=0.08)
    rx = np.array([p[0] for p in ridge])
    ry = np.array([p[1] for p in ridge])
    ex = np.array([p[0] for p in eave])
    ey = np.array([p[1] for p in eave])

    def channels(dr):
        n = 30
        for k in range(n + 1):
            t = k / n
            xe = ex[0] + (ex[-1] - ex[0]) * t
            xr = rx[0] + (rx[-1] - rx[0]) * t
            yr = float(np.interp(xr, rx, ry))
            ye = float(np.interp(xe, ex, ey))
            dr.line([(xr, yr), (xe, ye)], fill=(24, 22, 22, 170), width=6)
            dr.line([(xr - 7, yr), (xe - 9, ye)], fill=(196, 190, 176, 70), width=5)
        for f in np.linspace(0.18, 0.9, 6):  # tile course joints
            line = []
            for t in np.linspace(0, 1, 30):
                xe = ex[0] + (ex[-1] - ex[0]) * t
                xr = rx[0] + (rx[-1] - rx[0]) * t
                yr = float(np.interp(xr, rx, ry))
                ye = float(np.interp(xe, ex, ey))
                line.append((xr + (xe - xr) * f, yr + (ye - yr) * f + rnd.uniform(-1.5, 1.5)))
            dr.line(line, fill=(30, 28, 26, 70), width=3)

    ic.overlay(channels, m)
    for _ in range(14):  # weathering: lichen and damp patches
        x, y = rnd.uniform(ex[0], ex[-1]), rnd.uniform(min(ys), max(ys))
        ic.shade(ic.intersect(m, ic.mask("ellipse", (x - 30, y - 12, x + 30, y + 12))),
                 (150, 150, 110) if rnd.random() < 0.5 else (10, 10, 10), 0.14, blur=8)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, 0, (rx[0] + rx[-1]) * 0.42, SIZE))), (255, 244, 220), 0.10, blur=40)
    ic.line([tuple(p) for p in eave], 16, (54, 48, 44))
    ic.line([(x, y - 6) for x, y in eave], 5, (170, 164, 150, 160))
    ic.line([tuple(p) for p in ridge], 26, (58, 52, 48))
    ic.line([(x, y - 7) for x, y in ridge], 7, (160, 152, 140, 180))
    return m


def chaikin(pts, n: int = 3):
    """Round a polyline by corner cutting (endpoints kept)."""
    for _ in range(n):
        out = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            out += [(0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1), (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)]
        out.append(pts[-1])
        pts = out
    return pts


def packet(ic: Icon, x0: float, y0: float, x1: float, y1: float, top: float = 26) -> None:
    """Paper-wrapped tea packet (a block with a visible top face) with a red paper band."""
    d = top * 0.6
    ic.poly([(x0, y0), (x1, y0), (x1 + d, y0 - top), (x0 + d, y0 - top)], "#e6d8b0", "#c8b48a", edge=3)
    ic.rect((x0, y0, x1, y1), "#d2c294", "#9a865c", vertical=False, noise=0.2, edge=3)
    ic.poly([(x1, y0), (x1 + d, y0 - top), (x1 + d, y1 - top), (x1, y1)], "#8e7c52", "#6a5a3a", edge=3)
    mx = x0 + (x1 - x0) * 0.42
    ic.poly([(mx - 8, y0), (mx + 8, y0), (mx + 8 + d, y0 - top), (mx - 8 + d, y0 - top)], "#b84a32", "#8a3020", edge=0)
    ic.rect((mx - 8, y0, mx + 8, y1), "#a83e2a", "#6e2416", edge=0)
    ic.line([(x0 + 4, y0 + 2), (x1 - 2, y0 + 2)], 3, (250, 240, 214, 150))


def chest(ic: Icon, x0: float, y0: float, x1: float, y1: float, d: float = 26) -> None:
    """Wooden tea chest: board front lit from the left, a shadowed side, and a lid whose lighter,
    slightly overhanging edge sits over a dark gap."""
    ic.shade(ic.mask("ellipse", (x0 - 20, y1 - 30, x1 + d + 30, y1 + 22)), alpha=0.5, blur=10)
    ic.rect((x0, y0, x1, y1), "#a47246", "#5a3a1e", vertical=False, noise=0.26, edge=4)
    ic.poly([(x1, y0), (x1 + d, y0 - d), (x1 + d, y1 - d), (x1, y1)], "#5e3e22", "#3a2614", edge=4)
    for y in np.linspace(y0 + 40, y1 - 10, 3):
        ic.line([(x0 + 4, y), (x1 - 4, y)], 3, (50, 30, 16, 150))
    ic.line([(x0 + 3, y0 + 18), (x1 - 3, y0 + 18)], 5, (30, 18, 10, 200))  # gap under the lid
    lid = [(x0 - 8, y0 - 2), (x1 + 6, y0 - 2), (x1 + d + 6, y0 - d - 4), (x0 + d - 6, y0 - d - 4)]
    ic.poly(lid, "#c49464", "#946838", edge=4)
    ic.rect((x0 - 8, y0 - 2, x1 + 6, y0 + 14), "#b88656", "#7a522c", vertical=False, edge=3)
    ic.line([(x0 - 6, y0), (x1 + 4, y0)], 4, (236, 204, 150, 200))
    for x in (x0 + 10, x1 - 16):  # iron corner straps
        ic.rect((x, y0 + 16, x + 8, y1 - 4), "#5a5654", "#3a3634", edge=0)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.70
    ic.grade["mute"] = 0.84

    # ---- the tea hill behind, on the left: a summit behind the pavilion's left end, a lower
    # shoulder, and a rounded slope that reaches the ground near the left edge
    ctrl = [(20, 948), (40, 906), (62, 830), (90, 730), (126, 646), (176, 598), (236, 578), (286, 550),
            (322, 476), (360, 392), (406, 330), (456, 302), (530, 292), (620, 306), (720, 340), (800, 380),
            (860, 420)]
    crest = chaikin(ctrl, 3)
    crest = [(x, y + rnd.uniform(-3, 3)) for x, y in crest]
    cx_, cy_ = np.array([p[0] for p in crest]), np.array([p[1] for p in crest])

    def crest_y(x):
        return float(np.interp(x, cx_, cy_))

    front = [(860, 900)] + [(x, 936 + 10 * math.sin(math.pi * (x - 20) / 840)) for x in np.linspace(840, 40, 10)]
    H = ic.poly_mask(crest + front)
    ic.fill(H, "#80543a", "#3e2616", radial=(300, 300, 800), noise=0.34, chroma=0.12)
    for _ in range(50):
        x, y = rnd.uniform(40, 840), rnd.uniform(320, 930)
        ic.shade(ic.intersect(H, ic.mask("ellipse", (x - 14, y - 5, x + 14, y + 5))),
                 (255, 226, 190) if rnd.random() < 0.4 else (0, 0, 0), 0.16, blur=2)
    lip = [(x, crest_y(x)) for x in np.linspace(20, 250, 24)]
    ic.shade(ic.intersect(H, ic.poly_mask(lip + [(x + 10, y + 30) for x, y in lip[::-1]])), (214, 150, 100), 0.28, blur=6)

    rows = [(346, 0.56, 36), (396, 0.53, 42), (452, 0.5, 48), (514, 0.47, 54), (584, 0.44, 60),
            (660, 0.41, 66), (744, 0.38, 72), (836, 0.35, 78), (934, 0.32, 84)]
    for yc, kf, h in rows:
        lam, ph, amp = rnd.uniform(90, 140), rnd.uniform(0, 6.3), h * 0.07
        segs, cur = [], []
        for x in np.arange(0, 900, 8):
            y = yc + kf * (crest_y(x) - 294) + amp * math.sin(x / lam + ph)
            yy = int(min(max(y - h * 0.2, 0), SIZE - 1))
            inside = y < 950 and H.getpixel((int(x), yy)) and H.getpixel((int(min(x + 30, SIZE - 1)), yy)) and \
                H.getpixel((int(max(x - 30, 0)), yy))
            if inside:
                cur.append((float(x), y))
            elif cur:
                segs.append(cur)
                cur = []
        if cur:
            segs.append(cur)
        for base in segs:
            a, b = rnd.randint(0, 4), rnd.randint(0, 2)
            base = base[a:len(base) - b] if len(base) - a - b >= 6 else base
            if len(base) < 6:
                continue
            ic.shade(ic.poly_mask([(x, y - 10) for x, y in base] + [(x, y + h * 0.28) for x, y in base[::-1]]),
                     (20, 10, 4), 0.32, blur=h * 0.12)
            hedge(ic, base, h)
    ic.shade(ic.mask("ellipse", (-200, 200, 400, 900)), (255, 240, 200), 0.08, blur=80)

    # ---- the pavilion: stone floor, deep open interior, racks of trays, slim posts
    X0, X1 = 470, 990
    ic.shade(ic.mask("rectangle", (X0 - 80, 420, X0 + 40, 800)), alpha=0.35, blur=30)
    ic.rect((X0 + 10, 440, X1 - 10, 790), "#261a10", "#0e0906", edge=0)

    def slats(dr):
        for x in np.arange(X0 + 20, X1 - 10, 26):
            dr.line([(x + rnd.uniform(-2, 2), 440), (x, 790)], fill=(96, 74, 52, 34), width=4)

    ic.overlay(slats)
    # depth: the interior darkens towards its sides and under the roof
    ic.shade(ic.mask("rectangle", (X0, 440, X0 + 70, 790)), alpha=0.5, blur=26)
    ic.shade(ic.mask("rectangle", (X1 - 70, 440, X1, 790)), alpha=0.5, blur=26)
    # racks of withering trays standing inside, set back from the posts
    for cx in (622, 846):
        for x in (cx - 108, cx + 108):
            ic.rect((x - 4, 500, x + 4, 780), "#6a4c30", "#3a2816", vertical=False, edge=0)
    for k, y in enumerate((540, 628, 716)):
        for cx in (622, 846):
            ic.line([(cx - 112, y + 16), (cx + 112, y + 16)], 5, (64, 46, 28))
            tray(ic, cx + rnd.uniform(-6, 6), y, 100, 25, "fresh" if k < 2 or cx < 700 else "rolled", rim=8)
    ic.shade(ic.mask("rectangle", (X0, 440, X1, 560)), alpha=0.55, blur=18)
    # stone floor: a lit top surface and a shaded front face, raised above the ground
    ic.poly([(X0 - 14, 790), (X1 + 12, 790), (X1 + 22, 770), (X0 - 4, 770)], "#b8ac98", "#948876", edge=3)
    ic.rect((X0 - 14, 790, X1 + 12, 838), "#8c8070", "#5a5046", noise=0.28, edge=4)
    for x in np.arange(X0 + 40, X1, 92):
        ic.line([(x + rnd.uniform(-8, 8), 792), (x + rnd.uniform(-8, 8), 836)], 3, (50, 44, 38, 170))
    ic.line([(X0 - 12, 791), (X1 + 10, 791)], 4, (214, 204, 184, 170))
    ic.shade(ic.mask("rectangle", (X0 - 14, 826, X1 + 12, 840)), alpha=0.35, blur=4)
    # posts: slim, lit left face and shaded right face, on stone bases
    for x in (X0 + 10, 730, X1 - 10):
        ic.rect((x - 11, 430, x + 11, 776), "#7a4e30", "#4a2c1a", vertical=False, edge=3)
        ic.rect((x - 11, 430, x - 3, 776), "#b88660", "#946440", vertical=False, noise=0.2, edge=0)
        ic.rect((x - 17, 762, x + 17, 778), "#a89c88", "#6e6456", edge=3)
    ic.line([(X0, 450), (X1, 450)], 14, (92, 62, 40))
    ic.line([(X0, 444), (X1, 444)], 3, (170, 130, 90, 150))
    ic.shade(ic.mask("rectangle", (X0 - 20, 440, X1 + 20, 510)), alpha=0.35, blur=14)

    # ---- tiled roof with upswept corners
    ridge = [(548, 244), (580, 270), (880, 270), (912, 244)]
    eave = [(414, 378), (440, 414), (462, 434)] + [(x, 446 + 12 * math.sin(math.pi * (x - 480) / 500)) for x in
                                        np.linspace(480, 980, 12)] + [(990, 434), (1012, 414), (1030, 378)]
    tileroof(ic, ridge, eave)
    ic.shade(ic.poly_mask([(870, 250), (1030, 250), (1030, 470), (880, 470)]), alpha=0.18, blur=40)

    # ---- in front: a tray of fresh leaf on the slope, a tray of rolled tea, the tea chest
    tray(ic, 236, 884, 150, 46, "fresh", rim=14)
    tray(ic, 574, 930, 158, 48, "rolled", rim=16)
    chest(ic, 800, 858, 968, 996, 26)
    packet(ic, 812, 818, 894, 852, 26)
    packet(ic, 902, 816, 962, 846, 22)
