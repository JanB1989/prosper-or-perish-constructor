"""Olive Estate: a terraced hillside grove, stone-walled steps planted with olives, the estate house on top.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/olive_rotations/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/olive_rotations

Identity (tier 2 of the olive chain): three dry-stone terrace walls step up the slope, each level
planted with gnarled silver-green olives standing in tended rings of dark earth; a watering channel
runs along the middle terrace; on the top terrace the limewashed estate house with its tile roof and
a square dovecote tower. More structure than the farmstead: the whole hillside is worked.

Local helpers: the olive helpers of ``olive_farm`` and ``olive_farmstead`` plus ``terrace``
(retaining wall with coping and the planted level above it) and ``dovecote``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("terraces", "fruit_orchard", "farming_village", "noble_villa")

BARK = ("#a49a88", "#3c3329")
LEAF = ("#9aa47e", "#262e1e")
BLACK = ((56, 40, 50), (112, 92, 104), (22, 14, 20))
PURPLE = ((92, 46, 60), (140, 88, 100), (42, 18, 28))
GREENO = ((122, 130, 52), (172, 180, 96), (62, 68, 22))
TILE = ("#b8704a", "#6a3620")
LIME = ("#d2c5a4", "#a39272")
SHUTTER = ("#7a8668", "#48523c")


# ---------------------------------------------------------------- helpers
def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


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


def scaled(c, f: float):
    return tuple(int(max(0, min(255, v * f))) for v in rgb(c))


def tube(ic: Icon, ctrl, w0: float, w1: float, colors=BARK, twist: float = 1.3, fissures: int = 3) -> Image.Image:
    """Bark limb along control points, ``w0`` wide at the start and ``w1`` at the end: lit left,
    shaded right, fissures spiralling round it so the limb reads as twisted. Returns its mask."""
    rnd = ic.random
    pts = np.array(ctrl, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], 30)
    P = np.stack([np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])], 1)
    for _ in range(3):
        P[1:-1] = (P[:-2] + 2 * P[1:-1] + P[2:]) / 4
    d = np.gradient(P, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None] + 1e-6
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    if nrm[:, 0].mean() < 0:
        nrm = -nrm  # +nrm points to the right (shadow side)
    t = np.linspace(0, 1, len(P))
    ph = rnd.uniform(0, 6)
    w = (w0 + (w1 - w0) * t ** 0.8) / 2 * (1 + 0.14 * np.sin(t * 11 + ph))
    Rt, Lt = P + nrm * w[:, None], P - nrm * w[:, None]
    poly = [tuple(p) for p in Lt] + [tuple(p) for p in Rt[::-1]]
    m = ic.poly_mask(poly)
    xs = [p[0] for p in poly]
    ic.fill(m, colors[0], colors[1], (min(xs) - 10, max(xs) + 10), vertical=False, noise=0.34, chroma=0.08)
    half = [tuple(p) for p in P] + [tuple(p) for p in Rt[::-1]]
    tint(ic, ic.poly_mask(half), m, (20, 16, 12), 0.38, 5)

    def lines(dr):
        for k in range(fissures):
            f0 = rnd.uniform(-0.8, 0.8)
            ph2 = rnd.uniform(0, 6)
            q = [tuple(P[i] + nrm[i] * w[i] * max(-0.9, min(0.9, f0 + 0.7 * math.sin(t[i] * math.pi * twist + ph2))))
                 for i in range(len(P))]
            dr.line(q, fill=(34, 26, 20, 170), width=int(rnd.uniform(4, 7)))
            dr.line([(x - 4, y - 2) for x, y in q], fill=(214, 206, 186, 60), width=3)
        lit = [tuple(P[i] - nrm[i] * w[i] * 0.72) for i in range(len(P))]
        dr.line(lit, fill=(226, 220, 200, 70), width=5)

    ic.overlay(lines, m)
    for _ in range(int(cum[-1] / 90)):  # knots and lichen
        i = rnd.randint(2, len(P) - 3)
        x, y = P[i] + nrm[i] * w[i] * rnd.uniform(-0.5, 0.5)
        r = w[i] * rnd.uniform(0.18, 0.32)
        if rnd.random() < 0.5:
            tint(ic, ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), m, (24, 18, 14), 0.55, 2)
        else:
            tint(ic, ic.mask("ellipse", (x - r, y - r, x + r, y + r)), m, (200, 204, 170), 0.25, 3)
    return m


def clump_dabs(ic: Icon, bx, by, rx, ry, mask, n: int, tone: float = 1.0) -> None:
    """Narrow olive leaves: silvery undersides flashing on the lit top, dark green in the shade."""
    rnd = ic.random

    def paint(dr):
        for _ in range(n):
            a, r = rnd.uniform(0, 2 * math.pi), rnd.random() ** 0.6
            x, y = bx + math.cos(a) * rx * r, by + math.sin(a) * ry * r
            v = (y - by) / ry + 0.5 * (x - bx) / rx  # -1.5 lit .. +1.5 shade
            ang = rnd.uniform(0, 2 * math.pi)
            L = rnd.uniform(11, 17)
            if v < rnd.uniform(-1.0, 0.25):
                col = (int(192 * tone), int(200 * tone), int(174 * tone), 140)
            elif v < rnd.uniform(0.0, 0.9):
                col = (int(96 * tone), int(114 * tone), int(70 * tone), 160)
            else:
                col = (26, 34, 20, 150)
            c, s_ = math.cos(ang), math.sin(ang)
            dr.polygon([(x, y), (x + c * L * 0.5 - s_ * 3.5, y + s_ * L * 0.5 + c * 3.5), (x + c * L, y + s_ * L),
                        (x + c * L * 0.5 + s_ * 3.5, y + s_ * L * 0.5 - c * 3.5)], fill=col)

    ic.overlay(paint, mask)


def fringe(ic: Icon, bx, by, rx, ry, c1, c2, n: int) -> None:
    """Loose leaves sticking out of a clump's upper and side edge, so the crown edge reads feathery."""
    rnd = ic.random
    lit, dk = rgb(c1), rgb(c2)

    def paint(dr):
        for _ in range(n):
            a = rnd.uniform(math.pi * 0.95, math.pi * 2.05)
            x, y = bx + math.cos(a) * rx * rnd.uniform(0.9, 1.04), by + math.sin(a) * ry * rnd.uniform(0.9, 1.04)
            L = rnd.uniform(10, 16)
            out = a + rnd.uniform(-0.6, 0.6)
            f = 0.5 + 0.5 * max(0.0, -math.sin(a)) * (1 if math.cos(a) < 0.3 else 0.6)
            col = tuple(int(dk[i] + (lit[i] - dk[i]) * f) for i in range(3)) + (255,)
            dr.line([(x, y), (x + math.cos(out) * L, y + math.sin(out) * L * 0.8)], fill=col, width=8)

    ic.overlay(paint)


def crown_clumps(ic: Icon, clumps, tone: float = 1.0, density: float = 1.0) -> Image.Image:
    """Clumpy olive crown: separate cushions of foliage, lit from the upper left, dark underside."""
    m = blank()
    c1, c2 = scaled(LEAF[0], tone), scaled(LEAF[1], tone)
    for bx, by, rx, ry in sorted(clumps, key=lambda c: c[1]):
        bm = ic.poly_mask(ic.jitter(bx, by, rx, ry, 44, 0.09))
        ic.fill(bm, c1, c2, radial=(bx - rx * 0.6, by - ry * 0.8, max(rx, ry) * 2.6), noise=0.3, chroma=0.12)
        tint(ic, ic.mask("ellipse", (bx - rx * 1.1, by + ry * 0.15, bx + rx * 1.1, by + ry * 1.5)), bm, (12, 18, 8), 0.52, 14)
        clump_dabs(ic, bx, by, rx, ry, bm, int(rx * ry / 55 * density), tone)
        m = union(m, bm)
        fringe(ic, bx, by, rx, ry, c1, c2, int((rx + ry) / 16))
    return m


def olive_tree(ic: Icon, x: float, base: float, h: float, cw: float, tone: float = 1.0, split: bool = True,
               fruit: bool = False, girth: float = 1.0, depth: float = 0.26) -> Image.Image:
    """Gnarled olive: short hollow trunk splitting into twisting limbs, a wide clumpy crown.
    ``h`` is the height to the top of the crown, ``cw`` the crown half-width, ``depth`` the crown's
    half-height as a share of ``h``. Returns the tree mask."""
    rnd = ic.random
    fork = base - h * 0.42
    ry = h * depth
    cy = base - h * 0.96 + ry
    bark = (scaled(BARK[0], tone), scaled(BARK[1], tone))
    # clumps: a back layer, then the limbs, then a front layer
    ends = [(-0.78, 0.10), (-0.45, -0.40), (-0.05, -0.62), (0.40, -0.45), (0.80, 0.02)]
    back, front = [], []
    for u, v in ends:
        back.append((x + u * cw + rnd.uniform(-20, 20), cy + v * ry + rnd.uniform(-10, 10), cw * rnd.uniform(0.34, 0.44),
                     ry * rnd.uniform(0.55, 0.7)))
    for u, v in ((-0.55, 0.28), (-0.12, 0.05), (0.30, 0.25), (0.62, 0.38), (-0.30, -0.25), (0.15, -0.3)):
        front.append((x + u * cw + rnd.uniform(-16, 16), cy + v * ry + rnd.uniform(-8, 8), cw * rnd.uniform(0.26, 0.36),
                      ry * rnd.uniform(0.42, 0.56)))
    m = crown_clumps(ic, back, tone * 0.82, 0.8)
    # trunk: two or three strands twisting round each other, spread roots
    sw = h * 0.085 * girth
    strands = [(-sw * 1.1, -cw * 0.42, 0.9), (sw * 0.9, cw * 0.40, 1.0)] if split else [(0, 0, 1.2)]
    if split:
        strands.insert(1, (-sw * 0.1, cw * 0.05, 0.7))
    for k, (bx, ex, f) in enumerate(strands):
        ctrl = [(x + bx * 1.6, base + 6), (x + bx + rnd.uniform(-12, 12), base - h * 0.14),
                (x + bx * 0.3 + (ex * 0.2) + rnd.uniform(-20, 20), base - h * 0.28),
                (x + ex * 0.45, fork), (x + ex * 0.8, cy + ry * 0.1)]
        m = union(m, tube(ic, ctrl, sw * 2.3 * f, sw * 0.55 * f, bark))
    if split:  # dark hollow where the trunk has split
        hx, hy = x - sw * 0.2, base - h * 0.17
        hollow = ic.poly_mask(ic.jitter(hx, hy, sw * 0.35, sw * 1.0, 10, 0.15))
        ic.fill(hollow, "#231a14", "#0e0a08", (hy - sw, hy + sw), noise=0.2)
    # roots flare into the ground
    for dx in (-sw * 2.2, -sw * 0.8, sw * 1.4, sw * 2.4):
        m = union(m, tube(ic, [(x + dx * 0.4, base - sw * 0.9), (x + dx, base + 4), (x + dx * 1.5, base + sw * 0.25)],
                          sw * 0.9, sw * 0.3, bark, fissures=1))
    # small limbs reaching into the front clumps
    for bx, by, rx, ry2 in front[:4]:
        m = union(m, tube(ic, [(x + (bx - x) * 0.3, fork + 10), ((x + bx) / 2, (fork + by) / 2 + 6), (bx, by + ry2 * 0.3)],
                          sw * 0.7, sw * 0.25, bark, fissures=1))
    m = union(m, crown_clumps(ic, front, tone, 1.0))
    if fruit:
        items = []
        for bx, by, rx, ry2 in front + back:
            for _ in range(rnd.choice((0, 0, 1, 2))):
                a = rnd.uniform(0.2, math.pi - 0.2)
                items.append((bx + math.cos(a) * rx * 0.7, by + math.sin(a) * ry2 * 0.75, rnd.uniform(9, 11),
                              rnd.choice((BLACK, PURPLE, BLACK))))
        olives(ic, items, m)
    return m


def olives(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Oval drupes (x, y, r, palette) in one blended layer: dark rim, body, lit side, glint."""

    def paint(dr):
        for x, y, r, (mid, lit, dk) in sorted(items, key=lambda it: it[1]):
            rx, ry = r * 1.2, r * 0.9
            dr.ellipse((x - rx, y - ry, x + rx, y + ry), fill=dk + (255,))
            dr.ellipse((x - rx + 1.5, y - ry + 1, x + rx - 2.5, y + ry - 2.5), fill=mid + (255,))
            dr.ellipse((x - rx * 0.75, y - ry * 0.8, x + rx * 0.1, y + ry * 0.05), fill=lit + (200,))
            g = max(r * 0.2, 1.5)
            dr.ellipse((x - rx * 0.45 - g, y - ry * 0.45 - g, x - rx * 0.45 + g, y - ry * 0.45 + g), fill=(240, 230, 230, 200))

    ic.overlay(paint, clip)


def drystone(ic: Icon, pts, base="#b0a48c", dark="#6e6454", course: float = 30) -> Image.Image:
    """Dry-stone wall face (polygon): irregular flat stones in wavering courses, each shaded as a
    form with a dark gap below; no mortar. Returns the wall mask."""
    rnd = ic.random.uniform
    m = ic.poly_mask(pts)
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, base, dark, (y0, y1), noise=0.25, chroma=0.08)
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle((x0, y0, x1, y1), fill=(34, 28, 22, 150))
    y = y0 - rnd(0, course * 0.5)
    while y < y1:
        h = course * rnd(0.7, 1.2)
        x = x0 - rnd(0, course * 1.5)
        while x < x1:
            w = course * rnd(1.0, 2.4)
            j = lambda k=4: rnd(-k, k)  # noqa: E731
            q = [(x + 4 + j(), y + 4 + j()), (x + w * 0.5, y + 2 + j()), (x + w - 4 + j(), y + 4 + j()),
                 (x + w - 3 + j(), y + h - 5 + j()), (x + w * 0.5, y + h - 3 + j()), (x + 4 + j(), y + h - 5 + j())]
            t = rnd(0.82, 1.12)
            c = scaled(base, t)
            d.polygon(q, fill=c + (255,))
            d.line([q[5], q[0], q[1], q[2]], fill=(236, 228, 208, 110), width=4)
            d.line([q[2], q[3], q[4], q[5]], fill=(40, 32, 24, 160), width=5)
            x += w
        y += h
    clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    ys = np.linspace(y0, y1, 4)
    tint(ic, ic.mask("rectangle", (x0, ys[2], x1, y1 + 20)), m, (28, 30, 18), 0.30, 16)
    return m


def earth(ic: Icon, pts, c1="#9c8460", c2="#62503a", tufts: int = 60, stones_n: int = 26) -> Image.Image:
    """Dry stony ground: ochre earth with clods, pale stones and dry grass tufts."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, c1, c2, (y0, y1), noise=0.34, chroma=0.1)
    for _ in range(stones_n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0 + 10, y1 - 8)
        r = rnd.uniform(6, 14) * (0.7 + 0.5 * (y - y0) / max(y1 - y0, 1))
        s = ic.poly_mask(ic.jitter(x, y, r * 1.4, r, 7, 0.2))
        tint(ic, ic.mask("ellipse", (x - r * 1.6, y, x + r * 1.8, y + r * 1.2)), m, (20, 14, 8), 0.35, 3)
        ic.fill(ic.intersect(s, m), "#cfc4aa", "#8a806c", (y - r, y + r), noise=0.2)

    def grass(dr):
        for _ in range(tufts):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0 + 6, y1 - 4)
            for _ in range(7):
                a = rnd.uniform(-2.5, -0.6)
                L = rnd.uniform(10, 24)
                col = (196, 178, 112, 190) if rnd.random() < 0.6 else (110, 112, 60, 190)
                dr.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col, width=3)

    ic.overlay(grass, m)
    return m


def coppi(ic: Icon, pts, c1=TILE[0], c2=TILE[1], pitch: float = 30, course: float = 34) -> Image.Image:
    """Canal-tile roof plane (ridge left, ridge right, eave right, eave left): rounded tile runs down
    the slope with a lit flank and a dark channel, per-tile tone, lichen, a row of tile mouths at the
    eave. Returns the roof mask."""
    rnd = ic.random
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.22, chroma=0.1)
    rl, rr, er, el = (np.array(p, float) for p in pts)
    n = max(3, int(np.hypot(*(er - el)) / pitch))
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(n + 1):
        u = k / n
        top, bot = rl + (rr - rl) * u, el + (er - el) * u
        L = np.hypot(*(bot - top))
        steps = max(2, int(L / course))
        for j in range(steps):
            a, b = top + (bot - top) * j / steps, top + (bot - top) * (j + 1) / steps
            t = rnd.uniform(-1, 1)
            w = pitch * 0.5
            q = [(a[0] - w * 0.45, a[1]), (a[0] + w * 0.45, a[1]), (b[0] + w * 0.5, b[1]), (b[0] - w * 0.5, b[1])]
            d.polygon(q, fill=(255, 226, 196, int(t * 50)) if t > 0 else (30, 12, 6, int(-t * 70)))
            d.line([(b[0] - w * 0.55, b[1] - 3), (b[0] + w * 0.55, b[1] - 3)], fill=(40, 16, 8, 120), width=4)
        d.line([tuple(top + np.array([-pitch * 0.18, 0])), tuple(bot + np.array([-pitch * 0.2, 0]))],
               fill=(255, 222, 190, 80), width=6)
        d.line([tuple(top + np.array([pitch * 0.5, 0])), tuple(bot + np.array([pitch * 0.5, 0]))],
               fill=(34, 14, 8, 170), width=8)
    for _ in range(int(n * 0.8)):  # lichen and soot
        u, v = rnd.random(), rnd.random()
        p = rl + (rr - rl) * u + ((el + (er - el) * u) - (rl + (rr - rl) * u)) * v
        r = rnd.uniform(10, 26)
        col = (206, 196, 140, 70) if rnd.random() < 0.6 else (40, 30, 24, 70)
        d.ellipse((p[0] - r, p[1] - r * 0.6, p[0] + r, p[1] + r * 0.6), fill=col)
    clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, ic.poly_mask([tuple(rl), tuple(rr), tuple(rr + np.array([0, 26])), tuple(rl + np.array([0, 26]))]), m,
         (255, 230, 200), 0.15, 6)
    # tile mouths along the eave
    for k in range(n + 1):
        p = el + (er - el) * k / n
        ic.fill(ic.mask("ellipse", (p[0] - pitch * 0.42, p[1] - 12, p[0] + pitch * 0.42, p[1] + 12)), "#9a5634", "#4a2412",
                (p[1] - 12, p[1] + 12), noise=0.15)
        ic.fill(ic.mask("ellipse", (p[0] - pitch * 0.25, p[1] - 5, p[0] + pitch * 0.25, p[1] + 8)), "#221410", "#140a08",
                noise=0.1)
    return m


def plaster(ic: Icon, pts, c1=LIME[0], c2=LIME[1], patches: int = 3) -> Image.Image:
    """Limewashed rubble wall: warm uneven wash, grime streaks from the eave, flaked patches showing
    the stones, a damp darker foot. Returns the wall mask."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.08)
    for _ in range(int((x1 - x0) / 30)):  # uneven wash
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.uniform(20, 60)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), m,
             (255, 250, 236) if rnd.random() < 0.5 else (120, 100, 70), 0.14, 12)
    for _ in range(int((x1 - x0) / 60)):  # grime streaks
        sx = rnd.uniform(x0, x1)
        ln = rnd.uniform(0.15, 0.45) * (y1 - y0)
        tint(ic, ic.mask("rectangle", (sx - rnd.uniform(4, 12), y0, sx + rnd.uniform(4, 12), y0 + ln)), m, (70, 56, 40),
             rnd.uniform(0.10, 0.2), 6)
    for _ in range(patches):  # flaked limewash, rubble showing
        px, py = rnd.uniform(x0 + 40, x1 - 40), rnd.uniform(y0 + (y1 - y0) * 0.35, y1 - 40)
        patch = ic.intersect(m, ic.poly_mask(ic.jitter(px, py, rnd.uniform(34, 60), rnd.uniform(24, 40), 11, 0.3)))
        with ic.clipped(patch):
            drystone(ic, [(px - 80, py - 60), (px + 80, py - 60), (px + 80, py + 60), (px - 80, py + 60)],
                     "#a89478", "#6c5c48", course=20)
        edge = ImageChops.subtract(patch.filter(ImageFilter.MaxFilter(7)), patch)
        tint(ic, edge, m, (90, 76, 56), 0.4)
    tint(ic, ic.mask("rectangle", (x0, y1 - 90, x1, y1 + 30)), m, (60, 56, 36), 0.35, 24)
    return m


def shuttered(ic: Icon, x0, y0, x1, y1, shutter=SHUTTER) -> None:
    """Small deep window: stone surround, dark opening, two plank shutters folded open, sill."""
    w = x1 - x0
    ic.fill(ic.mask("rectangle", (x0 - 10, y0 - 10, x1 + 10, y1 + 12)), "#cfc4a8", "#9a8e74", (y0, y1), noise=0.2)
    ic.fill(ic.mask("rectangle", (x0, y0, x1, y1)), "#2c2622", "#120e0c", (y0, y1), noise=0.1)
    ic.shade(ic.mask("rectangle", (x0, y0, x1, y0 + 14)), alpha=0.5, blur=3)
    for sx0, sx1, lit in ((x0 - 10 - w * 0.5, x0 - 10, True), (x1 + 10, x1 + 10 + w * 0.5, False)):
        c = shutter if lit else (scaled(shutter[0], 0.8), scaled(shutter[1], 0.8))
        ic.fill(ic.mask("rectangle", (sx0, y0 - 6, sx1, y1 + 6)), c[0], c[1], (y0, y1), noise=0.22)
        for bx in np.linspace(sx0, sx1, 4)[1:-1]:
            ic.line([(bx, y0 - 4), (bx, y1 + 4)], 3, (30, 34, 24, 140))
        ic.outline([(sx0, y0 - 6), (sx1, y0 - 6), (sx1, y1 + 6), (sx0, y1 + 6)], 3, (30, 26, 20, 170))
        ic.shade(ic.mask("rectangle", (sx1 if lit else sx0 - 12, y0, (sx1 + 12) if lit else sx0, y1 + 10)), alpha=0.3, blur=5)
    ic.fill(ic.mask("rectangle", (x0 - 18, y1 + 6, x1 + 18, y1 + 20)), "#e2d8c0", "#a89c82", noise=0.15)
    ic.shade(ic.mask("rectangle", (x0 - 16, y1 + 20, x1 + 16, y1 + 34)), alpha=0.35, blur=5)


def terrace(ic: Icon, x0, x1, st, sb, wb, slope: float = 26) -> tuple[Image.Image, Image.Image]:
    """One terrace: the retaining wall face (``sb``..``wb``) with a coping course and a damp foot,
    and the level above it (``st``..``sb``) of dry earth. Wall ends are cut back into the slope.
    Returns (wall mask, surface mask)."""
    rnd = ic.random
    wall = [(x0, sb), (x1, sb), (x1 + slope * 0.6, wb), (x0 - slope * 0.6, wb)]
    W = drystone(ic, wall, "#bcaa88", "#76664e", course=24)
    tint(ic, ic.mask("rectangle", (x0 - 40, wb - 40, x1 + 40, wb + 10)), W, (28, 30, 18), 0.35, 14)
    surf = [(x0 + slope, st), (x1 - slope, st), (x1, sb), (x0, sb)]
    S = earth(ic, surf, "#9a8058", "#6e5a3c", tufts=int((x1 - x0) / 14), stones_n=int((x1 - x0) / 60))
    # coping: a row of flat capstones along the wall head, lit on top, shading the face below
    x = x0 - 4
    while x < x1:
        w = rnd.uniform(34, 60)
        cap = [(x + 2, sb - 6 + rnd.uniform(-2, 2)), (x + w - 2, sb - 6 + rnd.uniform(-2, 2)), (x + w, sb + 12),
               (x, sb + 12)]
        t = rnd.uniform(0.9, 1.1)
        ic.fill(ic.poly_mask(cap), scaled("#d6ccb2", t), scaled("#948a74", t), (sb - 6, sb + 12), noise=0.2)
        ic.line([cap[1], cap[2]], 3, (40, 32, 24, 150))
        x += w
    tint(ic, ic.mask("rectangle", (x0 - 40, sb + 12, x1 + 40, sb + 34)), W, (20, 14, 8), 0.45, 6)
    return W, S


def tended(ic: Icon, x, y, r, clip) -> None:
    """Hoed ring of dark earth round a tree's foot."""
    ic.fill(ic.intersect(clip, ic.poly_mask(ic.jitter(x, y, r, r * 0.26, 14, 0.12))), "#5e4630", "#3e2e1e",
            (y - r * 0.3, y + r * 0.3), noise=0.35)


def dovecote(ic: Icon, x0, x1, top, base) -> None:
    """Square limewashed dovecote tower: pigeon holes under a low pyramid tile roof."""
    m = plaster(ic, [(x0, top), (x1, top), (x1, base), (x0, base)], patches=1)
    tint(ic, ic.mask("rectangle", ((x0 + x1) / 2 + 10, top, x1 + 20, base)), m, (40, 30, 20), 0.18, 16)
    for row, y in enumerate((top + 30, top + 58)):
        for k in range(3):
            hx = x0 + (x1 - x0) * (k + 1) / 4 + (6 if row else 0)
            ic.fill(ic.mask("ellipse", (hx - 7, y - 8, hx + 7, y + 6)), "#1e1612", "#0e0a08")
            ic.line([(hx - 12, y + 9), (hx + 12, y + 9)], 4, (220, 210, 186))
    cx = (x0 + x1) / 2
    coppi(ic, [(cx - 6, top - 64), (cx + 6, top - 64), (x1 + 20, top + 4), (x0 - 20, top + 4)], pitch=24, course=26)
    ic.shade(ic.mask("rectangle", (x0, top + 6, x1, top + 36)), (30, 20, 12), 0.5, blur=8)
    ic.fill(ic.mask("ellipse", (cx - 12, top - 80, cx + 12, top - 58)), "#a85e3c", "#5a2c16")




def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.76
    ic.grade["mute"] = 0.96

    # ---- top terrace: the estate house and its dovecote, one old tree on the left
    W3, S3 = terrace(ic, 250, 950, 380, 426, 548)
    H0, H1, EAVE, BASE = 580, 910, 282, 412
    HW = plaster(ic, [(H0, EAVE - 8), (H1, EAVE - 8), (H1, BASE), (H0, BASE)], patches=2)
    tint(ic, ic.mask("rectangle", (H0 + 220, EAVE, H1 + 40, BASE)), HW, (40, 30, 20), 0.14, 30)
    ic.door(716, 334, 770, BASE - 2, arched=True, surround="#cdc2a6")
    shuttered(ic, 630, 326, 662, 366)
    shuttered(ic, 832, 326, 864, 366)
    coppi(ic, [(640, 180), (850, 180), (936, EAVE + 4), (556, EAVE + 4)], pitch=28, course=30)
    ic.shade(ic.mask("rectangle", (H0, EAVE + 10, H1, EAVE + 56)), (30, 20, 12), 0.5, blur=12)
    ic.line([(640, 180), (850, 180)], 14, (130, 70, 44))
    dovecote(ic, 500, 584, 176, BASE)
    tended(ic, 360, 404, 56, S3)
    olive_tree(ic, 360, 408, 230, 108, tone=0.9, girth=0.95, depth=0.33)

    # ---- middle terrace with its watering channel
    W2, S2 = terrace(ic, 130, 990, 564, 614, 748)
    ch = ic.intersect(S2, ic.mask("rectangle", (0, 596, SIZE, 608)))
    ic.fill(ch, "#8cb4bc", "#3e6470", (596, 608), noise=0.1)
    ic.shade(ic.intersect(S2, ic.mask("rectangle", (0, 592, SIZE, 598))), alpha=0.5, blur=2)
    for x in (250, 540, 840):
        tended(ic, x, 584, 52, S2)
        olive_tree(ic, x, 588, 240, 114, tone=0.95, split=x != 540, girth=0.95, depth=0.33)

    # ---- front terrace
    W1, S1 = terrace(ic, 24, 1004, 772, 828, 960)
    for x in (110, 395, 690, 930):
        tended(ic, x, 796, 56, S1)
        olive_tree(ic, x, 800, 260, 118, split=x in (110, 690), girth=0.95, depth=0.33)
