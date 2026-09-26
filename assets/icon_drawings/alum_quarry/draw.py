"""Alum Quarry (alum_quarry): a stepped face of dark alum shale with a smouldering calcining clamp.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/alum_quarry/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/alum_quarry

Identity: a quarry wall cut in ragged benches, blue-black shale in thin, slightly dipping beds broken
by joints under a pale sandstone overburden cap, small talus fans at the foot of each riser, and
beside it the calcining clamp: a lumpy heap of shale and brushwood burning slowly, roasted rust red,
a glowing seam along its crown and puffs of smoke drifting off to the upper right. A heap of raw
shale with a pick leaning on it sits in front. Vanilla pits are a treadwheel crane over a heap; the
iron mine is an adit in a rust-veined crag; this one reads through the benches, the grey-blue beds
and the red smoking heap. Local helpers: ``layer``/``composite``, ``tint``, ``ragged`` (uneven
edge with steps), ``bedded_face`` (tilted shale beds broken at joints), ``tread`` (bench top),
``talus`` (fan of shale chips), ``plate`` (split slab), ``clamp`` (roasting heap), ``puffs``
(separate smoke puffs), ``timber``, ``pick``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 31
REFS = ("stone_quarry", "clay_pit", "tar_kiln", "charcoal_maker")

SHALE, SHALE_DK = "#58667a", "#272e3c"      # alum shale, lit / shadow (blue-black)
TREAD, TREAD_DK = "#7e8692", "#4e5662"      # bench tops, weathered
SAND, SAND_DK = "#c2a672", "#86693e"        # sandstone overburden
BURNT, BURNT_DK = "#b86440", "#5e2a1a"      # calcined shale
WOOD, WOOD_DK = "#86603e", "#4e3522"
FLOOR, FLOOR_DK = "#7c7064", "#4e463e"


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


def ragged(ic: Icon, p, q, n: int = 10, jx: float = 4, jy: float = 5, steps: int = 2, step_h: float = 12) -> list:
    """Uneven edge from p to q: jittered points plus a few abrupt steps (slumps) along the way."""
    R = ic.random
    cuts = sorted(R.sample(range(2, n - 1), min(steps, max(n - 3, 0))))
    off, pts = 0.0, []
    for i, t in enumerate(np.linspace(0, 1, n)):
        x = p[0] + (q[0] - p[0]) * t + (R.uniform(-jx, jx) if 0 < i < n - 1 else 0)
        y = p[1] + (q[1] - p[1]) * t + (R.uniform(-jy, jy) if 0 < i < n - 1 else 0)
        if i in cuts:  # a step: two points at the same x, the edge drops or rises
            pts.append((x, y + off))
            off += R.choice((-1, 1)) * step_h * R.uniform(0.6, 1.1)
        pts.append((x, y + off * (1 - t) if i == n - 1 else y + off))
    return pts


def bedded_face(ic: Icon, pts, top: float, bottom: float, tilt: float = 3.0, joints: int = 3, stains: int = 3,
                c1=SHALE, c2=SHALE_DK, bed: tuple = (10, 40)) -> Image.Image:
    """Quarry face in thin sedimentary beds dipping by ``tilt`` degrees, broken into blocks by a few
    vertical joint cracks: each block has its own tone and its beds step by a small throw at the
    joint, bed lines stop short of the cracks, darker towards the foot. Returns the mask."""
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (top - 40, bottom + 60), noise=0.24, chroma=0.12)
    R = ic.random
    xs = [p[0] for p in pts]
    xa, xb = min(xs), max(xs)
    jx = sorted(R.uniform(xa + (xb - xa) * (k + 0.25) / joints, xa + (xb - xa) * (k + 0.8) / joints) for k in range(joints))
    edges = [xa - 30] + jx + [xb + 40]
    throw = [0.0]
    for _ in jx:
        throw.append(throw[-1] + R.uniform(-9, 9))
    slope = math.tan(math.radians(tilt))
    lay, d = layer()
    for k in range(len(edges) - 1):  # each joint block a slightly different tone
        t = R.uniform(-1, 1)
        d.rectangle((edges[k], top - 40, edges[k + 1], bottom + 40),
                    fill=(215, 225, 240, int(22 * t)) if t > 0 else (8, 10, 16, int(-40 * t)))
    y = top - (xb - xa) * abs(slope) + R.uniform(0, 10)
    while y < bottom + 10:
        h = R.uniform(*bed)
        t = R.uniform(-1, 1)
        for k in range(len(edges) - 1):
            if R.random() < 0.12:  # the parting dies out in this block
                continue
            g0 = edges[k] + (10 if k else 0) + R.uniform(0, 8)
            g1 = edges[k + 1] - 10 - R.uniform(0, 8)
            if g1 - g0 < 20:
                continue
            seg = [(x, y + (x - xa) * slope + throw[k] + R.uniform(-2, 2)) for x in np.linspace(g0, g1, max(3, int((g1 - g0) / 50)))]
            low = [(x, yy + h) for x, yy in seg[::-1]]
            d.polygon(seg + low, fill=(225, 232, 240, int(22 * t)) if t > 0 else (10, 12, 18, int(-40 * t)))
            d.line(seg, fill=(14, 16, 22, 120), width=3)
            d.line([(x, yy + 5) for x, yy in seg], fill=(200, 210, 222, 60), width=3)
        y += h
    for x in jx:  # joint cracks: dark zigzag, lit left lip, shadow to the right
        y0 = top + R.uniform(-4, (bottom - top) * 0.3)
        y1 = bottom - R.uniform(0, (bottom - top) * 0.3)
        path = [(x + R.uniform(-5, 5) + (yy - y0) * 0.06, yy) for yy in np.linspace(y0, y1, 4)]
        d.line([(px + 5, py) for px, py in path], fill=(8, 10, 14, 70), width=12)
        d.line(path, fill=(8, 10, 14, 200), width=5)
        d.line([(px - 5, py) for px, py in path], fill=(214, 222, 232, 70), width=3)
    composite(ic, lay, m)
    for _ in range(stains):  # sulphur-yellow efflorescence and rust weeping down from the beds
        sx = R.uniform(xa + 30, xb - 60)
        sy = R.uniform(top, bottom - 60)
        col = R.choice([(196, 160, 60), (170, 90, 44), (190, 150, 70)])
        ln = R.uniform(50, 110)
        streak = ic.poly_mask([(sx - 12, sy), (sx + 12, sy), (sx + 5, sy + ln), (sx - 4, sy + ln)])
        tint(ic, streak, m, col, R.uniform(0.3, 0.45), 5)
    tint(ic, ic.mask("rectangle", (0, bottom - 120, SIZE, bottom + 40)), m, (10, 10, 14), 0.35, 30)
    return m


def plate(ic: Icon, cx: float, cy: float, w: float, d: float, t: float, ang: float = 0,
          top=("#9aa0a6", "#6a7078"), edge=("#4a5058", "#262a30")) -> None:
    """Split shale slab: a flat lit top face and a thin dark front edge (``t`` thick)."""
    pts = [(-w / 2, -d / 2), (w / 2 - d * 0.3, -d / 2), (w / 2, d / 2), (-w / 2 + d * 0.3, d / 2)]
    tp = ic.rotate(pts, (cx, cy), ang)
    front = [tp[3], tp[2], (tp[2][0], tp[2][1] + t), (tp[3][0], tp[3][1] + t)]
    side = [tp[1], tp[2], (tp[2][0], tp[2][1] + t), (tp[1][0], tp[1][1] + t)]
    ic.poly(front, edge[0], edge[1], edge=0)
    ic.poly(side, edge[1], edge[1], edge=0)
    ic.fill(ic.poly_mask(tp), top[0], top[1], radial=(tp[0][0], tp[0][1], w * 1.2), noise=0.25)
    ic.line([tp[3], tp[2]], 3, (225, 230, 236, 110))
    ic.outline([tp[0], tp[1], side[2], front[2], front[3], tp[3]], 4, (30, 30, 34, 190))


def tread(ic: Icon, pts) -> Image.Image:
    """Bench top seen from the raised camera: lighter weathered shale, worn lit lip at the front."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, TREAD, TREAD_DK, (min(ys), max(ys)), noise=0.3, chroma=0.12)
    R = ic.random
    xs = [p[0] for p in pts]
    for _ in range(6):  # damp and grit patches
        x, y = R.uniform(min(xs), max(xs)), R.uniform(min(ys), max(ys))
        tint(ic, ic.poly_mask(ic.jitter(x, y, R.uniform(30, 60), 10, 8, 0.3)), m,
             R.choice([(30, 34, 42), (230, 234, 240)]), R.uniform(0.1, 0.2), 4)
    tint(ic, ic.mask("rectangle", (0, max(ys) - 22, SIZE, max(ys) + 4)), m, (240, 244, 248), 0.14, 5)  # worn lip
    return m


def talus(ic: Icon, x: float, y: float, w: float, h: float) -> None:
    """Small fan of fallen shale chips at the foot of a riser: apex at the wall, spreading forward."""
    R = ic.random
    fan = [(x - w * 0.18, y - 4), (x + w * 0.12, y - 6), (x + w * 0.5, y + h * 0.8), (x + w * 0.2, y + h),
           (x - w * 0.3, y + h * 0.95), (x - w * 0.5, y + h * 0.7)]
    fm = ic.poly_mask(fan)
    ic.fill(fm, "#6c7684", "#3a414e", (y, y + h), noise=0.35, chroma=0.1)
    tint(ic, ic.poly_mask([(x - w * 0.5, y + h * 0.7), (x - w * 0.18, y - 4), (x, y + h)]), fm, (230, 236, 244), 0.18, 4)
    lay, d = layer()
    for _ in range(int(w / 7)):
        cx = x + R.uniform(-w * 0.45, w * 0.45)
        cy = y + R.uniform(h * 0.2, h * 1.02)
        r = R.uniform(4, 9)
        q = [(cx - r, cy), (cx - r * 0.2, cy - r * 0.5), (cx + r, cy - r * 0.2), (cx + r * 0.3, cy + r * 0.45)]
        d.polygon(q, fill=(140, 148, 160, 220) if R.random() < 0.5 else (40, 44, 54, 220))
        d.line(q[:2], fill=(230, 236, 244, 150), width=2)
    composite(ic, lay, ic.poly_mask(fan).filter(ImageFilter.MaxFilter(9)))
    ic.shade(ic.mask("ellipse", (x - w * 0.55, y + h * 0.75, x + w * 0.55, y + h * 1.15)), (0, 0, 0), 0.25, blur=6)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared pole: lit upper half, darker lower half."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.outline(pts, 4, (40, 26, 16, 170))


def puff(ic: Icon, cx: float, cy: float, r: float, light, dark, edge_alpha: int = 110) -> Image.Image:
    """One cauliflower puff of smoke: a cluster of round lobes, lit top-left, grey belly."""
    R = ic.random
    m = ic.mask("ellipse", (cx - r * 0.85, cy - r * 0.5, cx + r * 0.85, cy + r * 0.55))
    for _ in range(7):
        a = R.uniform(math.pi * 0.8, math.pi * 2.2)
        lr = r * R.uniform(0.3, 0.55)
        lx, ly = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.4
        m = union(m, ic.mask("ellipse", (lx - lr, ly - lr * 0.9, lx + lr, ly + lr * 0.9)))
    ic.fill(m, light, dark, radial=(cx - r * 0.5, cy - r * 0.6, r * 1.9), noise=0.06, chroma=0.02)
    tint(ic, ic.mask("ellipse", (cx - r * 0.7, cy + r * 0.05, cx + r * 1.1, cy + r * 0.9)), m, (40, 36, 34), 0.22, r * 0.25)
    tint(ic, ic.mask("ellipse", (cx - r * 0.8, cy - r * 0.75, cx + r * 0.1, cy - r * 0.05)), m, (255, 252, 246), 0.2, r * 0.2)
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(5)))
    ic.shade(ring, (50, 46, 44), edge_alpha / 255)
    return m


def clamp(ic: Icon, x0: float, x1: float, base: float, top: float) -> Image.Image:
    """Calcining clamp seen from the raised camera: an uneven heap of shale and brushwood with a
    lumpy crest. Sloping front roasted rust red over raw grey shale at the foot, a darker
    smouldering crown with loose lumps on it, a bright glowing seam along the crown lip, ember vents
    at the foot. Returns the heap mask."""
    R = ic.random
    w = x1 - x0
    h = base - top
    crown = top + h * 0.34  # front edge of the crown

    def edge(p, q, n=8, j=8):
        return [(p[0] + (q[0] - p[0]) * t + R.uniform(-j, j), p[1] + (q[1] - p[1]) * t + R.uniform(-j * 0.6, j * 0.6))
                for t in np.linspace(0, 1, n)][:-1]

    def lumpy(p, q, n, amp):
        out = []
        for t in np.linspace(0, 1, n)[:-1]:
            out.append((p[0] + (q[0] - p[0]) * t + R.uniform(-4, 4),
                        p[1] + (q[1] - p[1]) * t - abs(math.sin(t * n * 1.3)) * amp * R.uniform(0.4, 1.2)))
        return out

    def flank(p, q, n=9, j=9, bulge=1.8):
        # convex heap flank from the foot p up to the shoulder q, lumpy
        return [(p[0] + (q[0] - p[0]) * s ** bulge + R.uniform(-j, j), p[1] + (q[1] - p[1]) * s + R.uniform(-j * 0.5, j * 0.5))
                for s in np.linspace(0, 1, n)][:-1]

    a, b = (x0, base), (x0 + w * 0.17, crown - 8)
    c, d = (x1 - w * 0.15, crown + 14), (x1, base)
    lip = [(b[0] + (c[0] - b[0]) * t + R.uniform(-3, 3), b[1] + (c[1] - b[1]) * t + 6 * math.sin(t * 7) + R.uniform(-3, 3))
           for t in np.linspace(0, 1, 9)[:-1]]
    front = flank(a, b, 9, 9, 1.5) + lip + flank(d, c, 9, 9, 1.7)[::-1] + [d, (x0 + w * 0.52, base + 6)]
    fm = ic.poly_mask(front)
    ic.fill(fm, BURNT, BURNT_DK, radial=(x0 + w * 0.3, crown, w * 0.9), noise=0.34, chroma=0.16)
    # raw grey shale creeping up from the foot
    foot = [(x0 - 10, base + 10)] + [(x0 + w * t, base - h * (0.3 + 0.08 * math.sin(t * 17 + 1))) for t in np.linspace(0, 1, 22)]
    foot += [(x1 + 10, base + 10)]
    tint(ic, ic.poly_mask(foot), fm, (72, 80, 92), 0.7, 10)
    # lumps: lit cap, shaded underside
    for _ in range(46):
        t = R.uniform(0.05, 0.95)
        yy = R.uniform(crown + 14, base - 10)
        xx = x0 + w * t
        r = R.uniform(18, 34)
        tint(ic, ic.poly_mask(ic.jitter(xx - r * 0.2, yy - r * 0.25, r * 0.7, r * 0.42, 8, 0.25)), fm, (255, 214, 180), 0.22, 3)
        tint(ic, ic.poly_mask(ic.jitter(xx + r * 0.15, yy + r * 0.4, r * 0.85, r * 0.3, 8, 0.25)), fm, (20, 8, 6), 0.38, 4)
    # form: left flank lit, right flank turned away, contact at the foot
    tint(ic, ic.poly_mask([a, b, (b[0] + 120, crown), (x0 + 130, base)]), fm, (255, 226, 190), 0.16, 26)
    tint(ic, ic.poly_mask([(x1 - w * 0.35, crown), c, d, (x1 - w * 0.4, base)]), fm, (14, 6, 4), 0.4, 36)
    tint(ic, ic.mask("rectangle", (x0, base - 36, x1, base + 10)), fm, (8, 6, 6), 0.4, 14)
    # crown: lumpy crest, smouldering, cracks glowing
    back = []
    for t in np.linspace(0, 1, 16)[1:-1]:  # heaped crest: irregular bumps, high in the middle
        back.append((b[0] + 10 + (c[0] - b[0] - 20) * t + R.uniform(-5, 5),
                     top + 22 - 8 * math.sin(math.pi * t) - R.uniform(0, 20) + (crown - top - 22) * (abs(t - 0.5) * 2) ** 4))
    cp = [b] + back + [c] + lip[::-1]
    cm = ic.poly_mask(cp)
    ic.fill(cm, "#74402c", "#3a1c14", (top, crown), noise=0.36, chroma=0.14)
    lay, dr = layer()
    for _ in range(5):
        sx = R.uniform(b[0] + 30, c[0] - 70)
        sy = R.uniform(top + 20, crown - 6)
        pts = [(sx, sy)]
        for _ in range(3):
            sx += R.uniform(18, 40)
            sy += R.uniform(-10, 10)
            pts.append((sx, sy))
        dr.line(pts, fill=(255, 130, 50, 190), width=14, joint="curve")
        dr.line(pts, fill=(255, 210, 130, 220), width=5, joint="curve")
    composite(ic, lay.filter(ImageFilter.GaussianBlur(3)), cm)
    ic.outline(cp, 4, (40, 22, 16, 170))
    # loose lumps on the crest, breaking the top edge
    for bx, by in back[2:-1:4]:
        ic.chunk(bx + R.uniform(-8, 8), by + R.uniform(2, 8), R.uniform(18, 26), "#a05a3c", "#4a2214", glint=(255, 190, 150))
    # the glowing seam along the crown lip
    glow, gd = layer()
    gd.line(lip + [c], fill=(255, 110, 30, 220), width=40, joint="curve")
    composite(ic, glow.filter(ImageFilter.GaussianBlur(9)))
    seam, sd = layer()
    sd.line(lip + [c], fill=(255, 150, 50, 255), width=18, joint="curve")
    sd.line([(x, y - 1) for x, y in lip + [c]], fill=(255, 232, 160, 255), width=8, joint="curve")
    composite(ic, seam.filter(ImageFilter.GaussianBlur(1.5)))
    # vents with ember glow at the foot
    for vx, vy, vr in ((x0 + w * 0.2, base - 34, 20), (x0 + w * 0.5, base - 30, 24), (x0 + w * 0.8, base - 38, 18)):
        ic.fill(ic.mask("ellipse", (vx - vr, vy - vr * 0.7, vx + vr, vy + vr * 0.7)), "#2a140c", "#120806", noise=0.1)
        ic.fill(ic.mask("ellipse", (vx - vr * 0.7, vy - vr * 0.3, vx + vr * 0.7, vy + vr * 0.5)), "#ffb458", "#c8421a",
                radial=(vx, vy + vr * 0.2, vr * 0.8), noise=0.1, chroma=0.04)
        tint(ic, ic.mask("ellipse", (vx - vr * 2.4, vy - vr * 2.2, vx + vr * 2.4, vy + vr * 1.2)), fm, (255, 140, 60), 0.22, 18)
    ic.outline(front, 5, (40, 22, 16, 200))
    # a few lumps rolled off at the foot
    for fx, fy, fr in ((x0 + 10, base - 10, 18), (x0 + w * 0.36, base - 8, 16)):
        ic.chunk(fx, fy, fr, "#9a5236", "#40180e", glint=(255, 190, 150))
    return ic.intersect(fm, fm)


def pick(ic: Icon, foot, top, span: float, thick: float, curve: float) -> None:
    """Pick leaning with its head up: long haft and a curved iron head across the top."""
    timber(ic, foot, top, 22, "#94704a", "#553a24")
    (fx, fy), (tx, ty) = foot, top
    L = math.hypot(tx - fx, ty - fy)
    ux, uy = (tx - fx) / L, (ty - fy) / L
    nx, ny = -uy, ux
    cx, cy = tx + ux * 8, ty + uy * 8
    ts = np.linspace(-1, 1, 21)

    def at(t, side):
        off = thick * (0.5 - 0.36 * abs(t)) * side
        return (cx + nx * span / 2 * t - ux * curve * t * t + ux * off,
                cy + ny * span / 2 * t - uy * curve * t * t + uy * off)

    head = [at(t, 1) for t in ts] + [at(t, -1) for t in ts[::-1]]
    hm = ic.poly_mask(head)
    ic.fill(hm, "#c4c8cc", "#4e5258", radial=(cx - span * 0.3, cy - thick, span * 0.8), noise=0.1, chroma=0.02)
    ic.line([at(t, 0.6) for t in ts], 4, (245, 248, 250, 150))
    ic.fill(ic.mask("ellipse", (cx - 16, cy - 16, cx + 16, cy + 16)), "#6e6a66", "#34302c", noise=0.1)  # eye/socket
    ic.outline(head, 5, (26, 26, 30, 230))


# ---- drawing -----------------------------------------------------------------------------------
def bench(ic: Icon, xl: float, xr: float, tread_y: float, face_y: float, foot: float, tilt: float,
          fans: tuple = ()) -> Image.Image:
    """One quarry bench: an uneven lit tread whose front edge slumps and steps, a chipped rounded
    right end and upper-left corner, talus fans at the back against the riser above, and the
    bedded face below it with a broken left edge."""
    R = ic.random
    front = ragged(ic, (xl + 16, face_y + R.uniform(-4, 4)), (xr - 16, face_y + 4), n=12, jy=5, steps=2, step_h=12)
    front += [(xr + 6, face_y + 14), (xr + 20, face_y + 32)]  # rounded, slumping right end
    back = ragged(ic, (xr - 34, tread_y + R.uniform(-4, 6)), (xl + 34, tread_y + 4), n=9, jy=4, steps=1, step_h=8)
    corner = [(xl + 18, tread_y + 10), (xl + 6, tread_y + 24), (xl + 10, (tread_y + face_y) / 2 + 6), (xl + 2, face_y - 8)]
    tr = back + corner + front + [(xr + 8, tread_y + (face_y - tread_y) * 0.4), (xr - 12, tread_y + 8)]
    tm = tread(ic, tr)
    ic.outline(tr, 4, (30, 30, 36, 150))
    for fx, fw in fans:  # talus against the riser above
        talus(ic, fx, tread_y + 2, fw, (face_y - tread_y) * 0.7)
    # face: top = tread front, right = broken rounded end, left = broken edge
    end = [front[-1]]
    for t in np.linspace(0, 1, 7)[1:]:
        end.append((xr + 20 + 20 * t + 12 * math.sin(math.pi * t) + R.uniform(-9, 9), face_y + 32 + (foot - face_y - 32) * t))
    left = [(xl + R.uniform(-4, 10), foot)]
    for yy in np.linspace(foot, face_y, 7)[1:-1]:
        left.append((xl + R.uniform(-14, 14), yy))
    face = front + end[1:] + left
    fm = bedded_face(ic, face, face_y, foot, tilt)
    tint(ic, ic.mask("rectangle", (0, face_y - 6, SIZE, face_y + 34)), fm, (0, 0, 0), 0.55, 10)  # lip shadow
    tint(ic, ic.poly_mask([(xr - 60, face_y), (xr + 70, face_y), (xr + 80, foot), (xr - 40, foot)]),
         fm, (4, 6, 10), 0.45, 26)  # broken end turns away from the light
    return union(tm, fm)


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95
    ic.grade["gamma"] = 0.66

    # smoke off the clamp crown: separate puffs widening and drifting up into the top-right corner,
    # paler towards the top; drawn first, the top one first, so each lower puff overlaps the next
    chain = ((926, 290, 86, "#c2bcb4", "#8a847c"), (882, 396, 74, "#aca69e", "#76706a"),
             (840, 482, 60, "#96908a", "#625c58"), (806, 552, 46, "#847e78", "#524c48"))
    for (ax, ay, ar, al, ad), (bx, by, br, _, _) in zip(chain, chain[1:]):  # necks joining the puffs
        puff(ic, (ax + bx) / 2 - 6, (ay + by) / 2 + 4, (ar + br) * 0.36, al, ad, edge_alpha=0)
    puff(ic, 786, 600, 30, "#7a746e", "#4a4440", edge_alpha=0)
    for cx, cy, r, lc, dc in chain:
        puff(ic, cx, cy, r, lc, dc, edge_alpha=60)

    # ---- top level: sandstone overburden over the first shale face
    capline = [(64, 344), (54, 318), (62, 300), (58, 288), (80, 272), (116, 262), (150, 270), (180, 266),
               (236, 250), (300, 260), (360, 250), (400, 268), (424, 300)]
    cap = capline + [(432, 350), (60, 352)]
    capm = ic.poly_mask(cap)
    ic.fill(capm, SAND, SAND_DK, (240, 350), noise=0.32, chroma=0.14)
    lay, d = layer()
    for y in (300, 326):
        d.line([(x, y + (x - 60) * 0.05 + ic.random.uniform(-5, 5)) for x in range(20, 480, 46)], fill=(80, 58, 32, 110), width=4)
    composite(ic, lay, capm)
    tint(ic, ic.poly_mask([(40, 240), (460, 240), (460, 286), (40, 296)]), capm, (255, 240, 210), 0.25, 10)
    for gx, gw in ((104, 60), (220, 80), (350, 70)):  # turf on the rim
        ic.poly(ic.jitter(gx, 266, gw * 0.6, 16, 9, 0.3), "#8a9454", "#56622e", edge=0)
    ic.outline(cap, 5, (40, 30, 22, 200))
    end_a = [(430, 348)]
    for t in np.linspace(0, 1, 7)[1:]:
        end_a.append((430 + 14 * t + 14 * math.sin(math.pi * t) + ic.random.uniform(-8, 8), 348 + 172 * t))
    face_a = [(62, 346), (430, 346)] + end_a[1:] + [(46, 520), (40, 486), (54, 452), (42, 420), (56, 386)]
    fa = bedded_face(ic, face_a, 346, 520, tilt=3.5, joints=3)
    tint(ic, ic.mask("rectangle", (0, 340, SIZE, 376)), fa, (0, 0, 0), 0.5, 10)
    tint(ic, ic.poly_mask([(360, 344), (470, 344), (490, 520), (380, 520)]), fa, (4, 6, 10), 0.45, 26)

    # ---- lower benches, each stepping out further to the right
    mb = bench(ic, 50, 520, 482, 544, 700, 3.0, fans=((180, 90), (390, 80)))
    mc = bench(ic, 30, 650, 664, 726, 884, 2.5, fans=((300, 96), (560, 84)))
    quarry = union(capm, fa, mb, mc)
    rim = ImageChops.subtract(quarry, quarry.filter(ImageFilter.MinFilter(25)))
    ic.shade(rim, alpha=0.2, blur=6)

    # ---- calcining clamp on the right, its shadow on the lowest bench
    ic.shade(ic.poly_mask([(560, 900), (600, 660), (690, 640), (700, 900)]), (0, 0, 0), 0.35, blur=24)
    clamp(ic, 570, 1014, 920, 590)

    # ---- quarry floor apron
    apron = [(20, 962), (48, 882), (600, 878), (700, 904), (640, 964)]
    am = ic.poly_mask(apron)
    ic.fill(am, FLOOR, FLOOR_DK, (878, 964), noise=0.34)
    tint(ic, ic.mask("rectangle", (0, 874, SIZE, 900)), am, (0, 0, 0), 0.35, 8)
    ic.outline(apron, 4, (40, 30, 24, 160))

    # ---- heap of raw shale waiting for the clamp, a big pick leaning on it
    ic.heap(40, 470, 950, 740, 40, 5, body=("#4a5362", "#232833"), lump=("#6c7888", "#262c38"),
            odd=("#8a7a58", "#3e3424"), odd_share=0.1)
    ic.shade(ic.mask("rectangle", (40, 900, 470, 960)), (0, 0, 0), 0.25, blur=16)
    plate(ic, 560, 944, 96, 22, 14, 6)
    pick(ic, (560, 952), (430, 718), 250, 40, 46)
