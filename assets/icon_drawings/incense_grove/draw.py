"""Incense Grove: gnarled frankincense trees on dry stony ground, resin tears on cut bark, the harvest
collected in a basket and on a drying mat.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/incense_grove/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/incense_grove

Identity: a squat frankincense tree with a swollen papery trunk twisting into bare crooked limbs
(some kinked at sharp elbows, one broken stub) that end in soft-edged tufts of crinkled grey-green
leaves of varied size; dark scraped bark wounds on the trunk and limbs weep deep amber drips with
bright glints; a smaller tree behind on the right; sunlit sandy ochre ground with rocks; in front a
light straw mat with irregular amber lumps of several sizes drying in clusters, and a basket heaped
with the same lumps.

Local helpers: ``limb`` (tapered crooked branch shaded as a form, peeling bark), ``tuft`` (cluster
of small crinkled leaflets at a twig end), ``tears`` (translucent resin drops with glints, optionally
running), ``cut`` (scraped bark wound with tears beneath), ``amber`` (irregular resin lumps), ``lumps``
(heap of them), ``gnarled_tree`` (trunk, limbs with optional sharp kink or broken stub, tufts, cuts).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 71
REFS = ("fruit_orchard", "perfumery", "caravanserai", "oma_falaj")

BARK = ("#a89a82", "#4a3e32")
TUFT = [((118, 138, 76), (160, 178, 108), (54, 66, 30)), ((104, 126, 70), (146, 166, 100), (46, 58, 26)),
        ((132, 146, 86), (176, 188, 120), (62, 72, 36))]
RESIN = [((216, 150, 48), (250, 204, 112), (116, 66, 12)), ((196, 118, 32), (238, 176, 84), (100, 50, 8)),
         ((228, 176, 74), (252, 222, 146), (136, 90, 22)), ((178, 98, 24), (226, 154, 66), (88, 40, 6))]


def blank() -> Image.Image:
    return Image.new("L", (SIZE, SIZE), 0)


def union(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.lighter(a, b)


def curve(ic: Icon, p0, p1, bend: float, n: int = 16):
    """Crooked branch path from p0 to p1: a bow of bend (fraction of its length) plus random
    kinks, smoothed so the elbows stay rounded."""
    rnd = ic.random
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = p1 - p0
    nrm = np.array([-d[1], d[0]])
    ctrl = [p0]
    for t in (0.25, 0.5, 0.75):
        ctrl.append(p0 + d * t + nrm * (bend * 4 * t * (1 - t) + rnd.uniform(-0.09, 0.09)))
    ctrl.append(p1)
    ctrl = np.array(ctrl)
    for _ in range(3):  # Chaikin smoothing, keeping the end points
        q = [ctrl[0]]
        for i in range(len(ctrl) - 1):
            q.append(ctrl[i] * 0.75 + ctrl[i + 1] * 0.25)
            q.append(ctrl[i] * 0.25 + ctrl[i + 1] * 0.75)
        q.append(ctrl[-1])
        ctrl = np.array(q)
    idx = np.linspace(0, len(ctrl) - 1, n).astype(int)
    return [tuple(ctrl[i]) for i in idx]


def limb(ic: Icon, pts, w0: float, w1: float, colors=BARK) -> Image.Image:
    """Tapered crooked branch along ``pts``: pale lit left flank, dark right flank, peeling bark
    flakes and a few cracks. Returns its mask."""
    rnd = ic.random
    P = np.array(pts, float)
    k = len(P)
    ws = [w0 + (w1 - w0) * (i / (k - 1)) ** 0.8 for i in range(k)]
    tang = np.gradient(P, axis=0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-6)
    nrm = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    if nrm[k // 2, 0] < 0:
        nrm = -nrm  # nrm points to the right (shadow side)
    right = [tuple(P[i] + nrm[i] * ws[i] / 2) for i in range(k)]
    left = [tuple(P[i] - nrm[i] * ws[i] / 2) for i in range(k)]
    outline = left + [tuple(P[-1] + tang[-1] * ws[-1] * 0.4)] + right[::-1]
    m = ic.poly_mask(outline)
    xs = [p[0] for p in outline]
    ic.fill(m, colors[0], colors[1], (min(xs), max(xs)), vertical=False, noise=0.3, chroma=0.14)
    shadow = [tuple(P[i] + nrm[i] * ws[i] * 0.1) for i in range(k)] + right[::-1]
    ic.shade(ic.poly_mask(shadow), (30, 20, 12), 0.45, blur=4)
    lit = [tuple(P[i] - nrm[i] * ws[i] * 0.42) for i in range(k)]
    ic.line(lit, max(3, int(w0 * 0.12)), (236, 228, 204, 110))

    def bark(dr):
        for _ in range(int(sum(ws) / 6)):
            i = rnd.randint(0, k - 2)
            f = rnd.uniform(-0.4, 0.4)
            c = P[i] + nrm[i] * ws[i] * f
            L = rnd.uniform(8, 22)
            e = c + tang[i] * L
            if rnd.random() < 0.55:
                dr.line([tuple(c), tuple(e)], fill=(232, 222, 196, 90), width=int(rnd.uniform(4, 8)))
            else:
                dr.line([tuple(c), tuple(e)], fill=(40, 28, 18, 110), width=3)

    ic.overlay(bark, m)
    ic.outline(outline, 3, (40, 28, 18, 140))
    return m


def tuft(ic: Icon, x: float, y: float, r: float, n: int = 34) -> None:
    """Clump of small crinkled leaves at a twig end: a shaded olive body, then pointed leaflets
    fanning outwards, back to front, lit from the upper left."""
    rnd = ic.random
    body = ic.poly_mask(ic.jitter(x, y - r * 0.05, r * 0.72, r * 0.46, 16, 0.22))
    ic.fill(body, "#6a7a44", "#232c12", radial=(x - r * 0.6, y - r * 0.6, r * 1.6), noise=0.3, chroma=0.12)
    items = []
    for _ in range(n):
        a = rnd.uniform(-math.pi * 1.15, math.pi * 0.15) if rnd.random() < 0.8 else rnd.uniform(0.2, math.pi - 0.2)
        d = r * rnd.uniform(0.2, 0.85) * (0.7 if a > 0.2 else 1.0)
        items.append((y + math.sin(a) * d * 0.6, x + math.cos(a) * d, a, rnd.choice(TUFT)))
    items.sort()

    def paint(dr):
        for ly, lx, a, (mid, lit, dk) in items:
            L, W = r * rnd.uniform(0.24, 0.46), r * rnd.uniform(0.09, 0.13)
            ca, sa = math.cos(a), math.sin(a) * 0.75
            tip = (lx + ca * L, ly + sa * L)
            side1 = (lx + ca * L * 0.45 - sa * W, ly + sa * L * 0.45 + ca * W)
            side2 = (lx + ca * L * 0.45 + sa * W, ly + sa * L * 0.45 - ca * W)
            shade = 1.0 + 0.35 * (-math.cos(a) * 0.5 - math.sin(a) * 0.5) - 0.25 * (ly - y) / r
            col = tuple(int(min(255, v * shade)) for v in mid)
            dr.polygon([(lx + 2, ly + 3), (side1[0] + 2, side1[1] + 3), (tip[0] + 2, tip[1] + 3),
                        (side2[0] + 2, side2[1] + 3)], fill=dk + (200,))
            dr.polygon([(lx, ly), side1, tip, side2], fill=col + (255,))
            dr.line([(lx, ly), tip], fill=lit + (120,), width=2)

    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    paint(ImageDraw.Draw(lay))
    lay.putalpha(lay.getchannel("A").filter(ImageFilter.GaussianBlur(1.6)))  # soft leafy edge, no stair steps
    ic.image.alpha_composite(lay)
    ic.shade(ic.mask("ellipse", (x - r, y, x + r, y + r * 0.7)), (20, 24, 8), 0.3, blur=10)


def tears(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Resin drops (x, y, r, palette, run): dark amber rim, deep amber body, lit side and a bright
    glint; ``run`` > 0 makes it a drip: a tapering tail running down into a heavy bulb."""

    def paint(dr):
        for x, y, r, (mid, lit, dk), run in items:
            if run:
                y2 = y + run
                tail = [(x - r * 0.22, y - r * 0.6), (x + r * 0.22, y - r * 0.6), (x + r * 0.8, y2 - r * 0.4),
                        (x - r * 0.8, y2 - r * 0.4)]
                dr.polygon([(px + 2, py + 2) for px, py in tail], fill=dk + (255,))
                dr.polygon(tail, fill=mid + (255,))
                dr.line([(x - r * 0.1, y - r * 0.4), (x - r * 0.45, y2 - r * 0.5)], fill=lit + (200,), width=3)
                y = y2
            dr.ellipse((x - r, y - r * 1.15, x + r, y + r), fill=dk + (255,))
            dr.ellipse((x - r * 0.8, y - r, x + r * 0.7, y + r * 0.7), fill=mid + (255,))
            dr.ellipse((x - r * 0.6, y - r * 0.85, x + r * 0.05, y - r * 0.1), fill=lit + (230,))
            g = max(r * 0.25, 1.8)
            dr.ellipse((x - r * 0.45 - g, y - r * 0.6 - g, x - r * 0.45 + g, y - r * 0.6 + g), fill=(255, 252, 236, 230))

    ic.overlay(paint, clip)


def cut(ic: Icon, x: float, y: float, w: float, h: float, drops: int = 3) -> None:
    """Scraped bark wound: pale raw wood with a dark rim, resin tears welling and running below."""
    rnd = ic.random
    wound = ic.jitter(x, y, w / 2, h / 2, 10, 0.14)
    ic.shade(ic.poly_mask([(px + 3, py + 5) for px, py in wound]), (20, 10, 4), 0.5, blur=4)
    ic.fill(ic.poly_mask(wound), "#7a5432", "#3a2210", radial=(x - w * 0.4, y - h * 0.4, w), noise=0.25)

    def scrape(dr):
        for k in range(4):
            yy = y - h * 0.3 + k * h * 0.2
            dr.line([(x - w * 0.35, yy), (x + w * 0.3, yy + rnd.uniform(-3, 3))], fill=(170, 130, 90, 90), width=3)

    ic.overlay(scrape, ic.poly_mask(wound))
    ic.outline(wound, 4, (40, 22, 10, 190))
    items = []
    for k in range(drops):
        items.append((x + w * (-0.3 + 0.6 * (k + rnd.uniform(0.2, 0.8)) / drops), y + h * 0.42 + rnd.uniform(0, h * 0.15),
                      rnd.uniform(11, 15), rnd.choice(RESIN[:2] + RESIN[3:]), rnd.choice((0, rnd.uniform(22, 40)))))
    tears(ic, items)


def amber(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Irregular resin lumps (x, y, r, palette), back to front: a jagged many-sided lump with a dark
    rim and underside, a lit facet at the upper left and a small bright glint."""
    rnd = ic.random
    shapes = []
    for x, y, r, pal in sorted(items, key=lambda it: it[1]):
        pts = ic.jitter(x, y, r * rnd.uniform(1.0, 1.3), r * rnd.uniform(0.72, 0.95), rnd.randint(8, 11), 0.17)
        shapes.append((pts, x, y, r, pal))

    def paint(dr):
        for pts, x, y, r, (mid, lit, dk) in shapes:
            dr.polygon([(px + 2, py + 3) for px, py in pts], fill=(60, 34, 10, 170))
            dr.polygon(pts, fill=dk + (255,))
            dr.polygon([(x + (px - x) * 0.8 - r * 0.08, y + (py - y) * 0.78 - r * 0.1) for px, py in pts],
                       fill=mid + (255,))
            dr.polygon([(x + (px - x) * 0.42 - r * 0.3, y + (py - y) * 0.38 - r * 0.32) for px, py in pts],
                       fill=lit + (220,))
            g = max(r * 0.16, 2.2)
            dr.ellipse((x - r * 0.45 - g, y - r * 0.5 - g, x - r * 0.45 + g, y - r * 0.5 + g), fill=(255, 248, 226, 235))

    ic.overlay(paint, clip)


SIZES = (7, 10, 14, 19)


def lumps(ic: Icon, cx: float, cy: float, rx: float, ry: float, n: int) -> None:
    """Heap of irregular resin pieces of three or four sizes on a dome."""
    rnd = ic.random
    items = []
    for _ in range(n):
        a, rr = rnd.uniform(math.pi, 2 * math.pi), rnd.random() ** 0.6
        items.append((cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr + rnd.uniform(0, ry * 0.5),
                      rnd.choice(SIZES) * rnd.uniform(0.9, 1.15), rnd.choice(RESIN)))
    amber(ic, items)


def gnarled_tree(ic: Icon, x: float, base: float, s: float, limbs, cuts, limb_cuts=()) -> Image.Image:
    """Frankincense tree: swollen, flaring trunk, crooked limbs (``limbs`` = start, end, bend, w0, w1,
    tuft size, in local units from the trunk foot; a start of (limb index, t, 0) forks off that
    limb), leaf tufts at the ends, scraped cuts."""
    acc = blank()
    trunk = [(x - 96 * s, base), (x - 68 * s, base - 40 * s), (x - 80 * s, base - 110 * s), (x - 58 * s, base - 170 * s),
             (x - 46 * s, base - 236 * s), (x + 42 * s, base - 240 * s), (x + 58 * s, base - 170 * s),
             (x + 84 * s, base - 100 * s), (x + 72 * s, base - 40 * s), (x + 104 * s, base)]
    tip, paths = [], []
    stubs = []
    for spec in limbs:
        start, (ex, ey), bend, w0, w1, tr = spec[:6]
        if len(start) == 2:
            p0 = (x + start[0] * s, base + start[1] * s)
        else:  # (parent limb index, position along it, 0): a fork growing out of that limb
            ppath = paths[start[0]][0]
            p0 = ppath[int(start[1] * (len(ppath) - 1))]
        p1 = (x + ex * s, base + ey * s)
        if len(spec) > 6:  # a sharp elbow: two straight runs meeting at the kink point
            k = np.array((x + spec[6][0] * s, base + spec[6][1] * s))
            a0, a1 = np.array(p0, float), np.array(p1, float)
            path = [tuple(a0 + (k - a0) * t) for t in np.linspace(0, 1, 8)]
            path += [tuple(k + (a1 - k) * t) for t in np.linspace(0, 1, 9)[1:]]
        else:
            path = curve(ic, p0, p1, bend)
        acc = union(acc, limb(ic, path, w0 * s, w1 * s))
        if tr:
            tip.append((p1, tr * s))
        else:
            stubs.append((p1, w1 * s))
        paths.append((path, w0 * s, w1 * s))
    tm = ic.poly_mask(trunk)
    ic.fill(tm, BARK[0], BARK[1], (x - 90 * s, x + 100 * s), vertical=False, noise=0.3, chroma=0.14)
    ic.shade(ic.poly_mask([(x + 10 * s, base), (x - 5 * s, base - 240 * s), (x + 42 * s, base - 240 * s),
                           (x + 84 * s, base - 100 * s), (x + 104 * s, base)]), (30, 20, 12), 0.4, blur=10)
    rnd = ic.random

    def bark(dr):
        for _ in range(int(60 * s)):
            yy = rnd.uniform(base - 230 * s, base - 10)
            xx = x + rnd.uniform(-66, 70) * s
            L = rnd.uniform(14, 40) * s
            if rnd.random() < 0.5:
                dr.line([(xx, yy), (xx + rnd.uniform(-6, 6), yy - L)], fill=(236, 226, 200, 90), width=int(rnd.uniform(5, 10)))
            else:
                dr.line([(xx, yy), (xx + rnd.uniform(-6, 6), yy - L)], fill=(40, 28, 18, 120), width=3)

    ic.overlay(bark, tm)
    ic.outline(trunk, 3, (40, 28, 18, 140))
    ic.shade(ic.intersect(tm, ic.mask("rectangle", (0, base - 60 * s, SIZE, base))), (40, 30, 16), 0.3, blur=14)
    for (px, py), w in stubs:  # broken-off limb: pale splintered end
        end = ic.jitter(px, py, w * 0.55, w * 0.4, 9, 0.25)
        ic.fill(ic.poly_mask(end), "#e2cea2", "#9a7c52", radial=(px - w * 0.4, py - w * 0.3, w), noise=0.2)
        ic.outline(end, 3, (50, 32, 16, 190))
    for (px, py), tr in sorted(tip, key=lambda t: t[0][1]):
        f = rnd.uniform(0.75, 1.25)
        tuft(ic, px, py, tr * 1.2 * f, int(40 * f))
        tuft(ic, px + tr * 0.6, py + tr * 0.25, tr * 0.8 * rnd.uniform(0.7, 1.2), 18)
    for cx, cy, w, h in cuts:
        cut(ic, x + cx * s, base + cy * s, w * s, h * s)
    for li, t in limb_cuts:  # wounds on the limbs themselves
        path, w0, w1 = paths[li]
        px, py = path[int(t * (len(path) - 1))]
        w = (w0 + (w1 - w0) * t) * 0.55
        cut(ic, px - w * 0.1, py, w, w * 0.8, 2)
    return union(acc, tm)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.68
    ic.grade["mute"] = 1.02

    # ---- dry stony ground: a pale ochre rise with rocks
    top = [(16, 900)] + [(x, 870 - 40 * math.sin(math.pi * (x - 16) / 1000) + rnd.uniform(-10, 8))
                         for x in np.linspace(60, 970, 14)] + [(1010, 880)]
    ground = top + [(1012, 998), (520, 1008), (14, 998)]
    ic.poly(ground, "#d4a866", "#8e6838", noise=0.34, edge=3)
    for _ in range(70):  # grit, pebbles and dry tufts
        x, y = rnd.uniform(40, 990), rnd.uniform(860, 994)
        r = rnd.uniform(5, 14)
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.5, x + r, y + r * 0.5)),
                 (255, 240, 210) if rnd.random() < 0.45 else (40, 28, 14), 0.2, blur=2)

    # ---- smaller tree behind on the right
    gnarled_tree(ic, 800, 860, 0.8, [
        ((-20, -210), (-240, -470), 0.22, 50, 18, 74),
        ((0, -230), (-40, -600), -0.16, 48, 16, 80),
        ((20, -220), (240, -500), -0.24, 48, 16, 74, (170, -262)),
        ((0, 0.5, 0), (-150, -560), -0.1, 22, 10, 56),
    ], [(0, -140, 64, 54)], [(2, 0.35)])

    # ---- the main frankincense tree: squat swollen trunk, crooked limbs forking again
    gnarled_tree(ic, 320, 930, 1.05, [
        ((-30, -210), (-236, -460), 0.25, 64, 22, 86, (-196, -250)),
        ((-10, -230), (-120, -660), -0.2, 58, 20, 96),
        ((10, -230), (90, -640), 0.18, 58, 20, 92),
        ((30, -210), (262, -490), -0.22, 64, 22, 88, (206, -254)),
        ((0, 0.45, 0), (-290, -600), 0.12, 30, 12, 70),
        ((1, 0.55, 0), (-10, -740), -0.1, 26, 10, 66),
        ((3, 0.5, 0), (330, -640), -0.15, 28, 12, 72),
        ((-50, -150), (-150, -196), 0.0, 36, 28, 0),
    ], [(-20, -100, 70, 60), (30, -196, 58, 50)], [(0, 0.3), (3, 0.35), (2, 0.45)])
    ic.shade(ic.mask("ellipse", (180, 890, 520, 950)), alpha=0.4, blur=14)

    # ---- stones half sunk in the grit
    for sx, sy, rx, ry in ((80, 944, 60, 34), (650, 900, 44, 24), (560, 972, 40, 22), (996, 910, 30, 20)):
        st = ic.jitter(sx, sy, rx, ry, 11, 0.12)
        ic.shade(ic.mask("ellipse", (sx - rx * 1.2, sy, sx + rx * 1.3, sy + ry * 1.2)), alpha=0.4, blur=6)
        ic.fill(ic.poly_mask(st), "#cbb690", "#6a5840", radial=(sx - rx * 0.7, sy - ry, rx * 2.2), noise=0.3)
        ic.shade(ic.poly_mask([(sx - rx * 0.6, sy - ry * 0.7), (sx + rx * 0.2, sy - ry * 0.9), (sx - rx * 0.1, sy)]),
                 (255, 246, 220), 0.25, blur=3)
        ic.outline(st, 3, (50, 38, 24, 150))

    # ---- drying mat of resin tears, front centre
    mpts = [(244, 916), (668, 908), (708, 1000), (206, 1004)]
    M = ic.poly_mask(mpts)
    ic.fill(M, "#e0c88c", "#ae9058", (908, 1004), noise=0.26)

    def weave(dr):
        for x in np.arange(236, 700, 44):
            x0 = x + rnd.uniform(-6, 6)
            dr.line([(x0, 906), (x0 + 66, 1004)], fill=(110, 80, 40, 90), width=4)
            dr.line([(x0 + 22, 906), (x0 - 24, 1004)], fill=(255, 244, 210, 70), width=3)

    ic.overlay(weave, M)
    ic.outline(mpts, 7, (120, 90, 50, 220))
    items = []
    for cx, cy, k, sp in ((296, 944, 10, 40), (390, 976, 14, 50), (516, 938, 8, 34), (604, 972, 13, 46),
                          (668, 934, 4, 20)):
        for _ in range(k):
            items.append((cx + rnd.uniform(-sp, sp), cy + rnd.uniform(-sp, sp) * 0.45,
                          rnd.choice(SIZES) * rnd.uniform(1.0, 1.35), rnd.choice(RESIN)))
    amber(ic, items, M)

    # ---- basket heaped with amber lumps, right
    ic.shade(ic.mask("ellipse", (750, 962, 1018, 1006)), alpha=0.45, blur=8)
    ic.fill(ic.mask("ellipse", (772, 846, 1004, 904)), "#6a4a1c", "#3a2810")
    lumps(ic, 888, 886, 112, 64, 70)
    ic.basket(768, 878, 1008, 1002, ("#b8925a", "#6c4e2c"))

    # ---- sun: warm light from the upper left, cast shadows of the sparse crown on the ground
    for _ in range(10):
        x, y = rnd.uniform(300, 900), rnd.uniform(880, 960)
        r = rnd.uniform(20, 40)
        ic.shade(ic.mask("ellipse", (x - r * 1.5, y - r * 0.4, x + r * 1.5, y + r * 0.4)), (60, 40, 20), 0.14, blur=10)
