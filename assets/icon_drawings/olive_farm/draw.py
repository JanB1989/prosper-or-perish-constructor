"""Olive Grove: two gnarled silver-green olive trees on a dry hillside, the harvest on a cloth below.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/olive_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/olive_farm

Identity (tier 0 of the olive chain): an old olive tree with a split, twisted grey trunk and a
clumpy silver-green crown dominates; a younger tree behind on the right, a low dry-stone wall across
the stony slope, a linen harvest cloth strewn with black olives under the big tree, a wicker basket
of olives at the bottom right. No buildings: the households come out to a bare grove.

Local helpers (shared by the four olive tiers): ``tube`` (twisting bark limb with fissures),
``olive_tree`` (gnarled split trunk, limbs, clumpy silver crown with narrow-leaf dabs), ``olives``
(small shaded drupes in one blended layer), ``drystone`` (irregular dry-stone courses),
``earth`` (dry stony ground with tufts).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("fruit_orchard", "farming_village", "terraces", "winery")

BARK = ("#a49a88", "#3c3329")
LEAF = ("#9aa47e", "#262e1e")
BLACK = ((56, 40, 50), (112, 92, 104), (22, 14, 20))
PURPLE = ((92, 46, 60), (140, 88, 100), (42, 18, 28))
GREENO = ((122, 130, 52), (172, 180, 96), (62, 68, 22))


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


def cloth(ic: Icon, pts, folds: int = 5) -> Image.Image:
    """Linen harvest cloth spread on the ground, soft folds and dirt."""
    rnd = ic.random
    m = ic.poly_mask(pts)
    x0, y0, x1, y1 = m.getbbox()
    ic.fill(m, "#c4b898", "#8a7e62", (y0, y1), noise=0.18, chroma=0.06)
    for k in range(folds):
        x = x0 + (k + 0.5) * (x1 - x0) / folds + rnd.uniform(-20, 20)
        fold = ic.poly_mask([(x - 8, y0), (x + 10, y0), (x + 30, y1), (x + 4, y1)])
        tint(ic, fold, m, (60, 50, 34) if k % 2 else (255, 250, 236), 0.28 if k % 2 else 0.18, 6)
    tint(ic, ic.mask("rectangle", (x0, y1 - 18, x1, y1 + 10)), m, (70, 58, 40), 0.3, 8)
    return m


def draw(ic: Icon) -> None:
    rnd = ic.random

    ic.grade["gamma"] = 0.76
    ic.grade["mute"] = 0.96
    # ---- stony slope and a tumbled dry-stone wall behind the young tree
    top = [(30, 880), (150, 858), (330, 866), (520, 850), (700, 836), (880, 828), (1010, 822)]
    ground = top + [(1016, 1000), (560, 1010), (14, 1000)]
    wall = [(520, 770), (560, 752), (640, 748), (700, 738), (800, 742), (880, 730), (960, 736), (1000, 744),
            (1004, 830), (800, 842), (620, 856), (520, 862)]
    drystone(ic, wall, course=26)
    G = earth(ic, ground, tufts=90, stones_n=34)
    ic.shade(ic.poly_mask([(520, 848), (1010, 816), (1010, 850), (520, 880)]), (20, 16, 10), 0.35, blur=10)

    # ---- younger tree behind on the right
    t2 = olive_tree(ic, 800, 868, 540, 210, tone=0.92, split=False)
    tint(ic, ic.mask("ellipse", (640, 840, 960, 896)), G, (18, 14, 8), 0.45, 12)

    # ---- harvest cloth under the big tree, strewn with fallen olives
    C = cloth(ic, [(120, 890), (620, 876), (720, 972), (70, 992)])
    fallen = []
    for _ in range(90):
        fx, fy = rnd.uniform(100, 690), rnd.uniform(886, 984)
        fallen.append((fx, fy, rnd.uniform(9, 11.5), rnd.choice((BLACK, BLACK, PURPLE, GREENO))))
    olives(ic, fallen, C)

    # ---- the old tree, contact shadow on the cloth
    olive_tree(ic, 380, 912, 840, 350)
    tint(ic, ic.mask("ellipse", (230, 880, 560, 940)), union(C, G), (18, 14, 8), 0.45, 14)

    # ---- basket of picked olives, bottom right
    ic.shade(ic.mask("ellipse", (806, 960, 1012, 1004)), alpha=0.45, blur=8)
    ic.fill(ic.mask("ellipse", (822, 846, 994, 896)), "#2a1e22", "#1a1014")
    heap = []
    for _ in range(70):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        heap.append((908 + math.cos(a) * 78 * rr, 876 + math.sin(a) * 40 * rr + rnd.uniform(0, 12), rnd.uniform(10, 12.5),
                     rnd.choice((BLACK, BLACK, PURPLE, GREENO))))
    olives(ic, heap)
    ic.basket(818, 872, 998, 996)
    # a beating pole lying across the cloth
    ic.line([(470, 990), (800, 900)], 14, (40, 28, 16, 140))
    ic.line([(466, 984), (796, 894)], 10, (150, 116, 76))
