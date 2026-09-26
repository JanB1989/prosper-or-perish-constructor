"""Alum Works (alum_works): open boiling house with steeping pits and a heap of roasted shale.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/alum_works/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/alum_works

Identity: the step up from the Alum Quarry. The roasted rust-red shale from the clamps (same colour
and lumpy crest as the quarry clamp) is heaped behind a row of timber-rimmed steeping pits sunk in
the yard, full of pale green liquor; a launder carries the liquor into the long, low boiling house,
whose open timber-framed front shows a large shallow lead pan over a glowing furnace arch. Soft
white steam leaves the roof louvre, darker smoke the brick stack, and a tub of white alum crystals
stands in front. Local helpers: layer/composite, tint, stones, shingles,
timber, puff/puff_chain (smoke and steam puffs), roasted_heap, pit (sunken pit
seen from above), crystal, tub, launder (open trough on posts), boiling_house.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 41
REFS = ("saltpeter_workshop", "dyes_workshop", "tar_kiln", "salt_collector")

BURNT, BURNT_DK = "#b86440", "#5e2a1a"      # calcined shale (shared with the quarry clamp)
LIQUOR, LIQUOR_DK = "#a8c2a4", "#5e8078"    # alum liquor, pale green
WOOD, WOOD_DK = "#8a6440", "#4e3522"
WALL, WALL_DK = "#b09e80", "#6e604c"
YARD, YARD_DK = "#86786a", "#564c42"


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


def stones(ic: Icon, box, base=WALL, dark=WALL_DK, course: float = 36, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.05) -> None:
    """Rubble wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay, d = layer()
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
    composite(ic, lay, m)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, soft course shadow."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone, td = layer()
    shadow = Image.new("L", (SIZE, SIZE), 0)
    sd = ImageDraw.Draw(shadow)
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
        td.line([(0, yl - 4), (SIZE, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (SIZE, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    composite(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam: lit upper half, darker lower half."""
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


def puff(ic: Icon, cx: float, cy: float, r: float, light, dark, edge_alpha: int = 0) -> Image.Image:
    """One cauliflower puff of smoke or steam: a cluster of round lobes, lit top-left, grey belly."""
    R = ic.random
    m = ic.mask("ellipse", (cx - r * 0.85, cy - r * 0.5, cx + r * 0.85, cy + r * 0.55))
    for _ in range(7):
        a = R.uniform(math.pi * 0.8, math.pi * 2.2)
        lr = r * R.uniform(0.3, 0.55)
        lx, ly = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.4
        m = union(m, ic.mask("ellipse", (lx - lr, ly - lr * 0.9, lx + lr, ly + lr * 0.9)))
    ic.fill(m, light, dark, radial=(cx - r * 0.5, cy - r * 0.6, r * 1.9), noise=0.05, chroma=0.02)
    tint(ic, ic.mask("ellipse", (cx - r * 0.7, cy + r * 0.05, cx + r * 1.1, cy + r * 0.9)), m, (60, 58, 56), 0.16, r * 0.3)
    tint(ic, ic.mask("ellipse", (cx - r * 0.8, cy - r * 0.75, cx + r * 0.1, cy - r * 0.05)), m, (255, 255, 252), 0.2, r * 0.25)
    if edge_alpha:
        ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(5)))
        ic.shade(ring, (50, 46, 44), edge_alpha / 255)
    return m


def puff_chain(ic: Icon, chain, neck: bool = True, edge_alpha: int = 50) -> None:
    """Puffs from the top (first) down to the source (last), joined by smaller necks."""
    if neck:
        for (ax, ay, ar, al, ad), (bx, by, br, _, _) in zip(chain, chain[1:]):
            puff(ic, (ax + bx) / 2, (ay + by) / 2 + 4, (ar + br) * 0.36, al, ad)
    for cx, cy, r, lc, dc in chain:
        puff(ic, cx, cy, r, lc, dc, edge_alpha)


def roasted_heap(ic: Icon, x0: float, x1: float, base: float, top: float) -> Image.Image:
    """Heap of roasted shale waiting for the pits: rust red, an uneven lumpy crest with clods lying
    on it, lit left, shadowed right, a darker burnt patch round the base."""
    R = ic.random
    w, h = x1 - x0, base - top
    ts = np.linspace(0, 1, 40)
    prof = []
    for t in ts:
        env = math.sin(math.pi * t ** 0.9) ** 0.7 * (1 - 0.18 * t)
        bump = (abs(math.sin(t * 23 + 1.3)) * 18 + R.uniform(0, 12)) * env
        prof.append((x0 + w * t, base - h * env + bump - (22 if 0.3 < t < 0.42 else 0) * env))
    pts = prof + [(x1, base + 6), (x0, base + 6)]
    m = ic.poly_mask(pts)
    ic.fill(m, BURNT, BURNT_DK, radial=(x0 + w * 0.3, top, w * 0.9), noise=0.34, chroma=0.16)
    for _ in range(60):
        t = R.uniform(0.05, 0.95)
        xx = x0 + w * t
        yy = R.uniform(top + 10, base - 8)
        r = R.uniform(18, 30)
        tint(ic, ic.poly_mask(ic.jitter(xx - r * 0.2, yy - r * 0.25, r * 0.7, r * 0.42, 8, 0.25)), m, (255, 214, 180), 0.3, 2)
        tint(ic, ic.poly_mask(ic.jitter(xx + r * 0.15, yy + r * 0.4, r * 0.85, r * 0.3, 8, 0.25)), m, (20, 8, 6), 0.5, 3)
    tint(ic, ic.mask("ellipse", (x0 + w * 0.5, top, x1 + 80, base + 60)), m, (14, 6, 4), 0.4, 40)
    # darker burnt rust round the base, blotchy
    for _ in range(9):
        bx = R.uniform(x0 + 20, x1 - 20)
        tint(ic, ic.poly_mask(ic.jitter(bx, base - 20, R.uniform(50, 90), R.uniform(26, 44), 9, 0.3)), m,
             (70, 22, 12), R.uniform(0.35, 0.5), 8)
    tint(ic, ic.mask("rectangle", (x0, base - 30, x1, base + 10)), m, (8, 6, 6), 0.35, 14)
    ic.outline(pts, 5, (40, 22, 16, 200))
    for k in range(3, len(prof) - 3, 5):  # clods on the crest
        px, py = prof[k]
        ic.chunk(px + R.uniform(-6, 6), py + R.uniform(4, 12), R.uniform(15, 24), "#a85e3e", "#4a2014", glint=(255, 190, 150))
    for cx, cy, r in ((x0 + 10, base - 6, 18), (x0 + w * 0.42, base + 2, 14), (x0 + w * 0.7, base - 2, 16)):
        ic.chunk(cx, cy, r, "#9a5236", "#40180e", glint=(255, 190, 150))
    return m


def pit(ic: Icon, x0: float, x1: float, yb: float, yf: float, skew: float = 18, rim: float = 12) -> Image.Image:
    """Sunken steeping pit seen from the raised camera: a thin plank rim flush with the yard, the
    dark far inner wall showing as a band, then the pale green liquor as a flat parallelogram with a
    soft sheen and a white crust line along its far edge."""
    R = ic.random
    def para(a0, a1, b, f, sk):
        return [(a0 + sk, b), (a1 + sk, b), (a1, f), (a0, f)]
    outer = para(x0, x1, yb, yf, skew)
    om = ic.poly_mask(outer)
    ic.shade(ic.poly_mask(para(x0 - 8, x1 + 10, yb - 4, yf + 10, skew)), (20, 12, 6), 0.3, blur=6)
    ic.fill(om, "#9a7450", "#5e4128", (yb, yf), noise=0.24)
    k = skew / (yf - yb)
    ib, iff = yb + rim * 0.7, yf - rim
    inner = [(x0 + rim + k * (yf - ib), ib), (x1 - rim + k * (yf - ib), ib), (x1 - rim + k * (yf - iff), iff), (x0 + rim, iff)]
    im = ic.poly_mask(inner)
    ic.fill(im, "#3a2618", "#24160c", (ib, ib + 20), noise=0.2)
    lq = ib + (iff - ib) * 0.4
    liquor = [(x0 + rim + k * (yf - lq), lq), (x1 - rim + k * (yf - lq), lq), (x1 - rim + k * (yf - iff), iff), (x0 + rim, iff)]
    lm = ic.poly_mask(liquor)
    ic.fill(lm, LIQUOR, LIQUOR_DK, (lq, iff + 20), noise=0.08, chroma=0.08)
    cx = x0 + (x1 - x0) * R.uniform(0.3, 0.45)
    tint(ic, ic.mask("ellipse", (cx - (x1 - x0) * 0.28, lq + 4, cx + (x1 - x0) * 0.22, iff - 6)), lm, (240, 250, 236), 0.35, 8)
    tint(ic, ic.mask("rectangle", (0, lq - 4, SIZE, lq + 14)), lm, (20, 36, 30), 0.45, 5)  # far wall shadow on the liquor
    ic.line([liquor[0], liquor[1]], 3, (232, 238, 222, 120))  # crust at the far edge
    tint(ic, ic.mask("rectangle", (0, iff - 10, SIZE, iff + 2)), lm, (20, 30, 26), 0.25, 4)
    for x in np.arange(x0 + 40, x1 - 20, 44):  # plank joints on the near rim
        ic.line([(x + R.uniform(-4, 4), iff), (x + R.uniform(-4, 4), yf)], 2, (40, 26, 14, 120))
    ic.line([inner[3], inner[2]], 3, (255, 236, 200, 110))  # lit near edge
    ic.outline(inner, 3, (30, 20, 12, 150))
    ic.outline(outer, 4, (40, 26, 16, 190))
    return om


def crystal(ic: Icon, cx: float, cy: float, r: float, ang: float = 0) -> None:
    """Octahedral alum crystal: four visible faces, lit upper left, cool translucent white."""
    top, bot = (0, -r), (0, r * 0.9)
    left, right, front = (-r * 0.8, 0), (r * 0.75, -r * 0.05), (r * 0.1, r * 0.2)
    faces = [((top, left, front), "#f4f2ec", "#d8d6d4"), ((top, front, right), "#dcdce2", "#b0b2bc"),
             ((left, bot, front), "#c8c8d0", "#9c9eaa"), ((front, bot, right), "#a8aab6", "#7a7c88")]
    for pts, c1, c2 in faces:
        p = ic.rotate(pts, (cx, cy), ang)
        ic.fill(ic.poly_mask(p), c1, c2, (cy - r, cy + r), noise=0.06, chroma=0.03)
    outline = ic.rotate([top, right, bot, left], (cx, cy), ang)
    ic.outline(outline, 3, (60, 60, 70, 170))


def tub(ic: Icon, x0: float, x1: float, top: float, base: float) -> None:
    """Low coopered tub heaped with alum crystals."""
    w = x1 - x0
    cx = (x0 + x1) / 2
    lip = w * 0.14
    body = [(x0, top), (x1, top), (x1 - w * 0.06, base)] + \
           [(cx + math.cos(a) * (w / 2 - w * 0.06), base + math.sin(a) * lip * 0.8) for a in np.linspace(0, math.pi, 14)] + \
           [(x0 + w * 0.06, base)]
    m = ic.poly_mask(body)
    ic.fill(m, "#a4764c", "#4c3120", radial=(x0 + w * 0.3, top, w * 1.0), noise=0.16)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top, x1 + 10, base + lip)), m, (16, 8, 4), 0.35, 12)
    for f in (0.3, 0.75):
        y = top + (base - top) * f
        ic.line([(cx + math.cos(a) * (w / 2 - w * 0.06 * f), y + math.sin(a) * lip * 0.8) for a in np.linspace(0, math.pi, 14)],
                9, (58, 54, 52))
    ic.fill(ic.mask("ellipse", (x0, top - lip, x1, top + lip)), "#5a3e26", "#3a2616", (top - lip, top + lip))
    # heap of crystals rising out of the tub
    heap = [(x0 + 8, top + 4), (x0 + w * 0.2, top - lip * 1.6), (cx, top - lip * 2.6), (x1 - w * 0.22, top - lip * 1.7),
            (x1 - 8, top + 4)]
    ic.fill(ic.poly_mask(heap), "#e6e4de", "#a6a8b0", radial=(x0 + w * 0.3, top - lip * 2.5, w * 0.8), noise=0.1)
    R = ic.random
    for _ in range(9):
        crystal(ic, R.uniform(x0 + w * 0.2, x1 - w * 0.2), R.uniform(top - lip * 2, top), R.uniform(14, 22),
                R.uniform(-25, 25))
    ic.outline(body, 4, (40, 26, 16, 170))


def launder(ic: Icon, A, B, width: float = 22, side: float = 16, posts: int = 3) -> None:
    """Open wooden trough on low posts carrying liquor from A to B: lit rim, dark near side, a
    pale green stripe of liquor running in it."""
    (ax, ay), (bx, by) = A, B
    for t in np.linspace(0.1, 0.9, posts):
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        timber(ic, (px, py + side), (px + 2, py + side + 26), 10)
    near = [(ax, ay + width / 2), (bx, by + width / 2), (bx, by + width / 2 + side), (ax, ay + width / 2 + side)]
    ic.poly(near, "#7a5636", "#4a321e", edge=0)
    top = [(ax, ay - width / 2), (bx, by - width / 2), (bx, by + width / 2), (ax, ay + width / 2)]
    ic.poly(top, "#a47c52", "#6a4a2c", edge=0)
    ic.line([(ax, ay), (bx, by)], int(width * 0.55), LIQUOR_DK)
    ic.line([(ax, ay - 2), (bx, by - 2)], int(width * 0.28), "#c4dac0")
    ic.outline([top[0], top[1], near[2], near[3]], 4, (40, 26, 16, 190))


def boiling_house(ic: Icon, X0: float, X1: float, EAVE: float, RIDGE: float, FOOT: float) -> None:
    """Long low rubble house open along its front: a timber-framed opening shows the dark interior,
    a large shallow lead boiling pan sitting on a brick furnace with a big glowing arch."""
    wall = ic.mask("rectangle", (X0, EAVE, X1, FOOT))
    stones(ic, (X0, EAVE, X1, FOOT))
    O0, O1, OT = X0 + 70, X1 - 110, EAVE + 50
    op = ic.mask("rectangle", (O0, OT, O1, FOOT))
    ic.fill(op, "#2e2018", "#140c08", (OT, FOOT), noise=0.2)
    tint(ic, ic.mask("ellipse", (O0 + 40, OT + 60, O1 - 40, FOOT + 120)), op, (200, 90, 40), 0.3, 40)  # furnace glow
    tint(ic, ic.mask("rectangle", (O0, OT, O1, OT + 50)), op, (0, 0, 0), 0.5, 14)  # dark under the roof
    # furnace: brick block with a large glowing arch
    F0, F1, FT = O0 + 40, O1 - 40, FOOT - 120
    fb = ic.mask("rectangle", (F0, FT, F1, FOOT))
    ic.fill(fb, "#9a5c44", "#4e2a1e", (FT, FOOT), noise=0.22)
    lay, d = layer()
    for i, y in enumerate(np.arange(FT + 4, FOOT, 20)):
        d.line([(F0, y), (F1, y)], fill=(50, 26, 18, 110), width=3)
        for x in np.arange(F0 + (i % 2) * 20, F1, 40):
            d.line([(x, y), (x, y + 20)], fill=(50, 26, 18, 80), width=2)
    composite(ic, lay, fb)
    ax0, ax1 = (F0 + F1) / 2 - 90, (F0 + F1) / 2 + 90
    arch = union(ic.mask("ellipse", (ax0, FT + 20, ax1, FT + 130)), ic.mask("rectangle", (ax0, FT + 75, ax1, FOOT)))
    ic.fill(arch, "#ffd060", "#c8360a", radial=((ax0 + ax1) / 2, FOOT - 10, 120), noise=0.12, chroma=0.04)
    tint(ic, ic.mask("rectangle", (ax0, FOOT - 40, ax1, FOOT)), arch, (255, 244, 190), 0.55, 10)  # white-hot bed
    tint(ic, ic.mask("ellipse", (ax0, FT + 20, ax1, FT + 90)), arch, (120, 30, 6), 0.45, 12)
    tint(ic, ic.mask("ellipse", (ax0 - 70, FT - 10, ax1 + 70, FOOT + 60)), fb, (255, 150, 60), 0.4, 22)
    ic.overlay(lambda dd: dd.arc((ax0, FT + 20, ax1, FT + 130), 180, 360, fill=(60, 30, 18, 220), width=6))
    ic.line([(ax0, FT + 75), (ax0, FOOT)], 5, (60, 30, 18, 220))
    ic.line([(ax1, FT + 75), (ax1, FOOT)], 5, (60, 30, 18, 220))
    # the pan: wide, shallow, lead grey rim, liquor inside, seen from slightly above
    P0, P1, PY = F0 - 26, F1 + 26, FT - 6
    side = [(P0, PY), (P1, PY), (P1 - 8, PY + 26), (P0 + 8, PY + 26)]
    ic.poly(side, "#8a8e94", "#44484e", edge=0)
    rim = ic.mask("ellipse", (P0, PY - 34, P1, PY + 14))
    ic.fill(rim, "#b4b8bc", "#6a6e74", (PY - 34, PY + 14), noise=0.08)
    inner = ic.mask("ellipse", (P0 + 14, PY - 26, P1 - 14, PY + 6))
    ic.fill(inner, "#9cb8a2", "#5e7e74", (PY - 26, PY + 6), noise=0.08)
    tint(ic, ic.mask("ellipse", (P0 + 50, PY - 22, P0 + 180, PY - 6)), inner, (240, 250, 240), 0.4, 5)
    ic.overlay(lambda dd: dd.ellipse((P0, PY - 34, P1, PY + 14), outline=(40, 40, 44, 200), width=4))
    ic.outline(side, 4, (40, 40, 44, 190))
    # steam off the pan, inside the dark house
    for sx, sy, r in ((P0 + 90, PY - 60, 26), (P0 + 160, PY - 76, 32), (P1 - 110, PY - 64, 28)):
        tint(ic, ic.mask("ellipse", (sx - r, sy - r * 0.8, sx + r, sy + r * 0.8)), op, (230, 228, 222), 0.35, 12)
    # timber frame of the opening: two posts, a lintel, knee braces
    timber(ic, (O0 - 6, OT - 4), (O1 + 6, OT - 4), 26)
    for x in (O0, O1):
        timber(ic, (x, OT), (x, FOOT), 24)
    timber(ic, (O0 + 4, OT + 60), (O0 + 60, OT + 4), 14)
    timber(ic, (O1 - 4, OT + 60), (O1 - 60, OT + 4), 14)
    tint(ic, ic.mask("rectangle", (X0, FOOT - 60, X1, FOOT)), wall, (26, 30, 20), 0.3, 16)
    tint(ic, ic.mask("rectangle", (O1, EAVE, X1 + 40, FOOT)), wall, (10, 6, 4), 0.25, 40)
    for gx in (X0 + 30, X1 - 60):  # soot and damp streaks from the eaves
        tint(ic, ic.mask("rectangle", (gx - 14, EAVE, gx + 14, EAVE + 120)), wall, (30, 24, 18), 0.18, 8)
    ic.outline([(X0, EAVE), (X1, EAVE), (X1, FOOT), (X0, FOOT)], 5)


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.68

    X0, X1, EAVE, RIDGE, FOOT = 50, 660, 560, 420, 830
    SX0, SX1, STOP = 540, 606, 250  # furnace stack on the right end of the roof

    # furnace smoke (darker grey, drifting right) and louvre steam (soft white, drifting left)
    puff_chain(ic, ((676, 150, 54, "#9e9890", "#68625c"), (628, 202, 40, "#8a847e", "#58524e"),
                    (590, 236, 26, "#7a746e", "#4a4440")), edge_alpha=60)
    puff_chain(ic, ((150, 206, 62, "#fbfaf7", "#dcdcd8"), (200, 288, 50, "#f6f5f1", "#d6d6d2"),
                    (244, 350, 36, "#f0efeb", "#cfcfcb")), edge_alpha=0)

    # ---- roasted shale heap behind, on the right
    roasted_heap(ic, 600, 1014, 800, 520)
    timber(ic, (900, 700), (960, 560), 12, "#9a7450", "#5e4128")  # shovel in the heap
    ic.poly([(944, 548), (986, 560), (970, 610), (936, 598)], "#7a7a80", "#3e3e44", edge=4)

    # ---- boiling house: brick stack, roof with louvre, open front
    ic.rect((SX0, STOP, SX1, 470), "#9a5c44", "#5e3426", vertical=False, edge=0)
    lay, d = layer()
    for i, y in enumerate(range(STOP + 10, 470, 20)):
        d.line([(SX0, y), (SX1, y)], fill=(50, 26, 18, 110), width=3)
        for x in range(SX0 + (i % 2) * 16, SX1, 32):
            d.line([(x, y), (x, y + 20)], fill=(50, 26, 18, 80), width=2)
    composite(ic, lay, ic.mask("rectangle", (SX0, STOP, SX1, 470)))
    tint(ic, ic.mask("rectangle", (SX1 - 26, STOP, SX1 + 2, 470)), ic.mask("rectangle", (SX0, STOP, SX1, 470)), (0, 0, 0), 0.35, 6)
    ic.rect((SX0 - 8, STOP - 14, SX1 + 8, STOP + 6), "#8a5a44", "#5a3626", edge=4)
    ic.ellipse((SX0 + 8, STOP - 12, SX1 - 8, STOP), "#1c1410", "#0c0806", edge=0)
    ic.outline([(SX0, STOP + 6), (SX1, STOP + 6), (SX1, 470), (SX0, 470)], 4)
    roof = [(X0 - 30, EAVE + 12), (X1 + 30, EAVE + 12), (X1 - 20, RIDGE), (X0 + 24, RIDGE + 6)]
    shingles(ic, roof, "#a4684e", "#5e3626", course=30, stagger=40)
    # louvre on the ridge: small roofed vent with dark slats
    ic.rect((206, 366, 298, 424), "#6e5238", "#46321f", edge=4)
    for y in (378, 392, 406):
        ic.line([(212, y), (292, y + 4)], 6, (28, 20, 14))
    ic.poly([(192, 370), (312, 370), (286, 342), (218, 342)], "#9a6048", "#6a3e2c", edge=4)
    boiling_house(ic, X0, X1, EAVE + 10, RIDGE, FOOT)
    ic.shade(ic.mask("rectangle", (X0, EAVE + 10, X1, EAVE + 50)), (0, 0, 0), 0.45, blur=10)  # eave shadow

    # ---- yard with the pits sunk into it
    yard = [(30, 962), (36, 822), (560, 814), (1012, 790), (1016, 962)]
    ym = ic.poly_mask(yard)
    ic.fill(ym, YARD, YARD_DK, (790, 962), noise=0.34, chroma=0.12)
    tint(ic, ic.mask("rectangle", (0, 780, SIZE, 846)), ym, (0, 0, 0), 0.35, 14)  # contact under walls/heap
    ic.outline(yard, 4, (40, 30, 24, 160))
    # launder along the back of the pits into the boiling house
    launder(ic, (1000, 836), (X1 - 4, 812))
    pit(ic, 430, 628, 862, 948, skew=20)
    pit(ic, 640, 826, 858, 942, skew=18)
    pit(ic, 838, 1004, 854, 936, skew=16)
    # a paddle resting in the middle pit
    timber(ic, (716, 924), (790, 800), 12, "#9a7450", "#5e4128")

    # ---- tub of alum crystals in front of the house, loose crystals beside it
    tub(ic, 70, 290, 870, 950)
    for cx, cy, r, a in ((322, 936, 22, 10), (358, 952, 16, -20), (300, 958, 14, 30)):
        crystal(ic, cx, cy, r, a)
