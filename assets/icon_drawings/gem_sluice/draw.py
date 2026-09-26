"""Gem Sluice (gem_sluice): a long timbered sluice box on trestles washing gravel into a stream.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/gem_sluice/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/gem_sluice

Identity: the step up from the Gem Gravel Pit (same gravel, pebbles, timber and stones). A plank
sluice box runs diagonally across the picture on trestles, from an open slatted funnel hopper of
gravel (fed by a feeder launder from the upper left) down to the stream; the water runs in one band
with froth breaking over the riffles and spills off the end into a splash that throws up spray. On
the bank in front a sorting table holds the coloured stones, with a basket of gravel. Local helpers:
layer/composite, tint, timber, planks, pebbles, gem, wicker, spout
(water jet with a splash), sluice (trough with riffles and flowing water), trestle, table
(sorting table), mist (spray thrown up by the splash), hopper (open slatted funnel box).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 61
REFS = ("irrigation_systems", "sand_pit", "sawmill", "jewelry_guild")

GRAVEL, GRAVEL_DK = "#9c8a70", "#554632"
PEBBLES = [(168, 156, 138), (140, 132, 120), (182, 162, 124), (120, 110, 98), (160, 120, 88), (196, 186, 166),
           (110, 116, 118), (150, 140, 110)]
WATER, WATER_DK = "#86aeb2", "#3e6468"
WOOD, WOOD_DK = "#8a6440", "#4e3522"
GEMS = [("#d8404a", "#6a1018"), ("#4a6ad8", "#141e6a"), ("#46b870", "#0e4a26"), ("#e0a030", "#6a3a08"),
        ("#b050c0", "#4a1256")]


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


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Pole or squared beam: lit upper half, darker lower half."""
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


def pebbles(ic: Icon, m: Image.Image, box, r: tuple = (7, 16), density: float = 1.0, scale_y: tuple = (0.7, 1.0),
            palette=PEBBLES) -> None:
    """Gravel texture inside mask ``m``: rounded pebbles of mixed colour, each with a lit cap and a
    dark underside, smaller towards the top (further away)."""
    x0, y0, x1, y1 = box
    R = ic.random
    lay, d = layer()
    n = int((x1 - x0) * (y1 - y0) / 260 * density)
    items = []
    for _ in range(n):
        y = R.uniform(y0, y1)
        f = scale_y[0] + (scale_y[1] - scale_y[0]) * (y - y0) / max(y1 - y0, 1)
        items.append((R.uniform(x0, x1), y, R.uniform(*r) * f))
    for x, y, rr in sorted(items, key=lambda p: p[1]):
        c = R.choice(palette)
        k = R.uniform(0.85, 1.1)
        col = tuple(int(min(255, v * k)) for v in c)
        box_ = (x - rr, y - rr * 0.72, x + rr, y + rr * 0.72)
        d.ellipse((box_[0] + 2, box_[1] + 4, box_[2] + 3, box_[3] + 5), fill=(30, 24, 18, 80))  # contact shadow
        d.ellipse(box_, fill=col + (215,))
        d.ellipse((x - rr * 0.7, y - rr * 0.6, x + rr * 0.2, y - rr * 0.05), fill=(255, 250, 238, 50))
        d.arc(box_, 10, 170, fill=(30, 24, 18, 70), width=3)
    composite(ic, lay, m)


def gem(ic: Icon, cx: float, cy: float, r: float, colors) -> None:
    """Small bright stone: faceted outline, darker lower facets, a pale table and a white glint."""
    pts = [(cx - r, cy - r * 0.2), (cx - r * 0.5, cy - r * 0.75), (cx + r * 0.5, cy - r * 0.75), (cx + r, cy - r * 0.2),
           (cx, cy + r * 0.85)]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1], (cy - r, cy + r), noise=0.05, chroma=0.02)
    ic.shade(ic.poly_mask([(cx, cy + r * 0.85), (cx + r, cy - r * 0.2), (cx + r * 0.1, cy - r * 0.1)]), (0, 0, 0), 0.3)
    table = [(cx - r * 0.45, cy - r * 0.55), (cx + r * 0.45, cy - r * 0.55), (cx + r * 0.3, cy - r * 0.2), (cx - r * 0.3, cy - r * 0.2)]
    ic.shade(ic.poly_mask(table), (255, 255, 255), 0.35)
    ic.overlay(lambda d: d.ellipse((cx - r * 0.5, cy - r * 0.62, cx - r * 0.2, cy - r * 0.38), fill=(255, 255, 255, 230)))
    ic.outline(pts, 3, (30, 20, 20, 190))


def wicker(ic: Icon, x0: float, x1: float, top: float, base: float) -> None:
    """Wicker basket heaped with gravel."""
    w = x1 - x0
    lip = w * 0.16
    ic.basket(x0, top, x1, base, ("#b89058", "#6a4c2a"))
    heap = [(x0 + 4, top + 2), (x0 + w * 0.2, top - lip * 1.1), (x0 + w * 0.55, top - lip * 1.6), (x1 - w * 0.18, top - lip),
            (x1 - 4, top + 2)]
    hm = ic.poly_mask(heap)
    ic.fill(hm, GRAVEL, GRAVEL_DK, (top - lip * 2, top), noise=0.2)
    pebbles(ic, hm, (x0, top - lip * 1.8, x1, top + 4), r=(7, 12), density=1.4, scale_y=(1, 1))
    ic.fill(ic.mask("rectangle", (x0 - 2, top - 6, x1 + 2, top + 10)), "#c29a64", "#7a5634", (x0, x1), vertical=False)
    ic.outline([(x0 - 2, top - 6), (x1 + 2, top - 6), (x1 + 2, top + 10), (x0 - 2, top + 10)], 3, (40, 26, 16, 190))


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, along=None) -> Image.Image:
    """Board panel: per-board tone and grain; boards run along ``along`` (a direction vector) or
    vertically. Returns the mask."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    if along is None:
        xs = [p[0] for p in pts]
        v = min(xs)
        while v < max(xs):
            w = board * R.uniform(0.8, 1.2)
            t = R.uniform(-1, 1)
            d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
            v += w
    else:
        ux, uy = along
        nx, ny = -uy, ux
        cx, cy = pts[0]
        for k in range(-40, 40):
            off = k * board
            p0 = (cx + nx * off - ux * 2000, cy + ny * off - uy * 2000)
            p1 = (cx + nx * off + ux * 2000, cy + ny * off + uy * 2000)
            t = R.uniform(-1, 1)
            q = [p0, p1, (p1[0] + nx * board, p1[1] + ny * board), (p0[0] + nx * board, p0[1] + ny * board)]
            d.polygon(q, fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
            d.line([p0, p1], fill=(35, 22, 12, 120), width=3)
    composite(ic, lay, m)
    return m


def spout(ic: Icon, x: float, y: float, dx: float, dy: float, w: float = 16) -> None:
    """Water jet leaving an opening at (x, y), arcing by (dx, dy), with a splash where it lands."""
    ts = np.linspace(0, 1, 18)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    lay, d = layer()
    d.line(path, fill=(170, 210, 220, 230), width=int(w + 8), joint="curve")
    d.line(path, fill=(236, 246, 247, 240), width=int(w), joint="curve")
    d.line([(px - 2, py - w * 0.2) for px, py in path[2:]], fill=(255, 255, 255, 170), width=max(3, int(w * 0.3)))
    ex, ey = path[-1]
    for _ in range(14):
        r = ic.random.uniform(5, 12)
        sx, sy = ex + ic.random.uniform(-w * 2.4, w * 2.4), ey + ic.random.uniform(-w * 1.4, w * 0.4)
        d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(240, 248, 248, 210))
    d.ellipse((ex - w * 2.8, ey - w * 0.5, ex + w * 2.8, ey + w * 0.7), fill=(232, 244, 245, 200))
    ic.image.alpha_composite(lay)


def trestle(ic: Icon, top, foot_y: float, spread: float, width: float = 18) -> None:
    """A-frame support under the trough: two splayed legs and a cross brace."""
    x, y = top
    timber(ic, (x - 6, y), (x - spread, foot_y), width)
    timber(ic, (x + 6, y), (x + spread * 0.6, foot_y + 10), width)
    yb = y + (foot_y - y) * 0.55
    timber(ic, (x - spread * 0.6, yb), (x + spread * 0.4, yb + 6), width * 0.7)


def sluice(ic: Icon, A, B, depth: float = 64, far=(14, -66)) -> tuple:
    """Plank trough from A (upper end) to B (lower end) seen from the raised camera: the near side
    wall, the far wall's inner face above the rushing water, riffle bars with white water below
    each, and a lit near rim. Returns (trough mask, unit direction)."""
    (ax, ay), (bx, by) = A, B
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    fx, fy = far
    # near side wall, below the axis
    side = [A, B, (bx, by + depth), (ax, ay + depth)]
    sm = planks(ic, side, "#94693f", "#4e3420", board=depth / 3, along=(ux, uy))
    tint(ic, ic.poly_mask([(ax, ay + depth * 0.6), (bx, by + depth * 0.6), (bx, by + depth), (ax, ay + depth)]), sm,
         (10, 6, 2), 0.35, 8)
    # the far wall's inner face and the water inside
    top = [A, B, (bx + fx, by + fy), (ax + fx, ay + fy)]
    tm = ic.poly_mask(top)
    ic.fill(tm, "#5a3e28", "#3a2818", (min(ay, by) + fy, max(ay, by)), noise=0.2)
    water = [(ax, ay - 4), (bx, by - 4), (bx + fx * 0.84, by + fy * 0.84), (ax + fx * 0.84, ay + fy * 0.84)]
    wm = ic.poly_mask(water)
    ic.fill(wm, "#6e929c", "#3e5c66", (min(ay, by) + fy, max(ay, by)), noise=0.06, chroma=0.04)
    R = ic.random
    # one continuous band: darker under the far wall, a lighter sheen along the middle of the flow
    tint(ic, ic.poly_mask([(ax + fx * 0.6, ay + fy * 0.6), (bx + fx * 0.6, by + fy * 0.6), (bx + fx, by + fy), (ax + fx, ay + fy)]),
         wm, (20, 40, 50), 0.4, 8)
    tint(ic, ic.poly_mask([(ax + fx * 0.25, ay + fy * 0.25), (bx + fx * 0.25, by + fy * 0.25), (bx + fx * 0.45, by + fy * 0.45),
                           (ax + fx * 0.45, ay + fy * 0.45)]), wm, (220, 236, 238), 0.25, 10)
    # riffles at uneven spacing: a faint dark bar under the water, froth breaking over it and
    # trailing downstream in broken diagonal streaks of different lengths
    lay, d = layer()
    t = 0.06
    while t < 0.95:
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        d.line([(px, py - 4), (px + fx * 0.84, py + fy * 0.84)], fill=(40, 60, 64, 40), width=4)
        for _ in range(R.randint(2, 5)):  # froth breaking over the riffle: small scattered foam flecks
            s = R.uniform(0.05, 0.85)
            cx, cy = px + fx * s + ux * R.uniform(0, 18), py + fy * s + uy * R.uniform(0, 18)
            r = R.uniform(4, 8)
            d.ellipse((cx - r * 1.6, cy - r * 0.6, cx + r * 1.6, cy + r * 0.6), fill=(244, 250, 250, int(R.uniform(140, 210))))
        for _ in range(R.randint(3, 5)):  # broken, wavy streaks trailing downstream
            s = R.uniform(0.08, 0.8)
            ln = R.uniform(30, 100)
            p0 = (px + fx * s + ux * 14, py + fy * s + uy * 14)
            pts = []
            for k in range(5):
                f = k / 4
                w = R.uniform(-0.03, 0.03) + f * R.uniform(-0.05, 0.03)
                pts.append((p0[0] + ux * ln * f + fx * w, p0[1] + uy * ln * f + fy * w))
            d.line(pts[:3], fill=(236, 246, 246, 200), width=5, joint="curve")
            d.line(pts[2:], fill=(236, 246, 246, 130), width=3, joint="curve")
        for _ in range(2):  # darker runs of deeper water between
            s = R.uniform(0.15, 0.8)
            ln = R.uniform(40, 80)
            p0 = (px + fx * s + ux * 30, py + fy * s + uy * 30)
            d.line([p0, (p0[0] + ux * ln, p0[1] + uy * ln)], fill=(30, 56, 66, 70), width=6)
        t += R.uniform(0.08, 0.15)
    for _ in range(int(L / 26)):  # scattered small flecks along the flow
        t0, s = R.uniform(0, 1), R.uniform(0.1, 0.8)
        pa = (ax + (bx - ax) * t0 + fx * s, ay + (by - ay) * t0 + fy * s)
        ln = R.uniform(10, 30)
        d.line([pa, (pa[0] + ux * ln, pa[1] + uy * ln)], fill=(232, 244, 246, 120), width=3)
    composite(ic, lay.filter(ImageFilter.GaussianBlur(1.8)), wm)
    # rims: far rim beam, lit near rim
    timber(ic, (ax + fx, ay + fy), (bx + fx, by + fy), 12, "#8e6844", "#5a3e26")
    timber(ic, A, B, 16, "#a87c50", "#6a4a2c")
    ic.outline(side, 4, (40, 26, 16, 190))
    return union(sm, tm), (ux, uy)


def table(ic: Icon, x0: float, x1: float, top: float, depth: float, foot: float) -> None:
    """Sorting table on the bank: plank top seen from above with a raised lip, wet sand, stones."""
    for lx in (x0 + 16, x1 - 20):
        timber(ic, (lx, top + depth - 6), (lx + 2, foot), 16)
    tp = [(x0 + 14, top), (x1 + 6, top), (x1, top + depth), (x0, top + depth)]
    tm = planks(ic, tp, "#a47a50", "#6a4a2c", board=24)
    sand = ic.poly_mask(ic.jitter((x0 + x1) / 2 - 20, top + depth * 0.52, (x1 - x0) * 0.34, depth * 0.3, 12, 0.12))
    tint(ic, sand, tm, (120, 110, 94), 0.75, 3)
    pebbles(ic, ic.intersect(sand, tm), (x0, top, x1, top + depth), r=(5, 9), density=0.8, scale_y=(1, 1))
    front = [(x0, top + depth), (x1, top + depth), (x1, top + depth + 16), (x0, top + depth + 16)]
    ic.poly(front, "#6a4a2c", "#4a3220", edge=0)
    ic.outline(tp + [], 4, (40, 26, 16, 190))
    ic.outline(front, 3, (40, 26, 16, 170))
    for (fx, fy, r), c in zip(((0.2, 0.35, 20), (0.45, 0.6, 22), (0.7, 0.3, 18), (0.82, 0.62, 17), (0.33, 0.72, 15)), GEMS):
        gem(ic, x0 + (x1 - x0) * fx, top + depth * fy, r, c)


def mist(ic: Icon, x: float, y: float, h: float) -> None:
    """Spray thrown up where the jet lands: a low cloud on the water and three fans of spray
    rising and thinning out, pale blue-white, shaded on the right; droplets only over painted parts."""
    R = ic.random
    m = ic.mask("ellipse", (x - 100, y - 44, x + 100, y + 30))
    for ang, reach in ((-128, 0.7), (-96, 1.0), (-62, 0.8)):
        a = math.radians(ang + R.uniform(-5, 5))
        for k in range(8):
            t = k / 7
            r = 40 * (1 - t) + 10
            cx = x + math.cos(a) * h * reach * t + R.uniform(-6, 6)
            cy = y - 20 + math.sin(a) * h * reach * t + R.uniform(-6, 6)
            m = union(m, ic.mask("ellipse", (cx - r, cy - r * 0.85, cx + r, cy + r * 0.85)))
    ic.fill(m, "#f2f7f8", "#9cb8c0", radial=(x - 40, y - h * 0.8, h * 1.3), noise=0.05, chroma=0.02)
    tint(ic, ic.mask("rectangle", (x + 20, y - h, x + 200, y + 40)), m, (40, 70, 84), 0.25, 30)
    tint(ic, ic.mask("rectangle", (x - 200, y - 10, x + 200, y + 40)), m, (60, 100, 112), 0.25, 12)
    lay, d = layer()
    for _ in range(40):
        a = R.uniform(math.pi * 1.1, math.pi * 1.9)
        rr = R.uniform(20, h * 0.8)
        px, py = x + math.cos(a) * rr, y - 20 + math.sin(a) * rr
        r = R.uniform(4, 7)
        d.ellipse((px - r, py - r, px + r, py + r), fill=(250, 252, 252, 230))
    composite(ic, lay, m)


def hopper(ic: Icon, x0: float, x1: float, top: float, bx0: float, bx1: float, bot: float) -> None:
    """Open funnel-shaped hopper box: wide plank top, narrow bottom, open slatted front showing the
    gravel inside, gravel heaped low in it and spilling over the front rim."""
    R = ic.random
    front = [(x0, top), (x1, top), (bx1, bot), (bx0, bot)]
    fm = ic.poly_mask(front)
    # gravel seen between the slats
    ic.fill(fm, GRAVEL, GRAVEL_DK, (top, bot), noise=0.3)
    pebbles(ic, fm, (x0, top, x1, bot), r=(7, 12), density=1.1, scale_y=(1, 1))
    tint(ic, fm, None, (20, 14, 8), 0.3)
    # slats: three boards across the front with gaps, following the funnel sides
    def lerp_side(y):
        f = (y - top) / (bot - top)
        return x0 + (bx0 - x0) * f, x1 + (bx1 - x1) * f
    for ya, yb in ((top + 6, top + 44), (top + 66, top + 102), (top + 124, bot)):
        l0, r0 = lerp_side(ya)
        l1, r1 = lerp_side(yb)
        board = [(l0, ya), (r0, ya), (r1, yb), (l1, yb)]
        planks(ic, board, "#9a6e44", "#5a3c22", board=200)
        ic.line([(l0, ya + 3), (r0, ya + 3)], 3, (255, 226, 180, 90))
        ic.shade(ic.poly_mask([(l1, yb), (r1, yb), (r1, yb + 8), (l1, yb + 8)]), (10, 6, 2), 0.5, blur=3)
        ic.outline(board, 3, (40, 26, 16, 170))
    for f in (0.0, 1.0):  # corner posts along the slanted sides
        timber(ic, (x0 + (x1 - x0) * f, top - 6), (bx0 + (bx1 - bx0) * f, bot + 4), 18, "#8e6844", "#5a3e26")
    tint(ic, ic.poly_mask([((x0 + x1) / 2 + 20, top), (x1 + 10, top), (bx1 + 10, bot), ((bx0 + bx1) / 2, bot)]), fm,
         (10, 6, 2), 0.2, 20)
    # open top: the far rim, low heaped gravel, gravel spilling over the front rim
    far = top - 50
    opening = [(x0 + 20, far), (x1 - 20, far), (x1, top), (x0, top)]
    om = ic.poly_mask(opening)
    ic.fill(om, "#5a4632", "#3a2c1e", (far, top), noise=0.2)
    heap = [(x0 + 4, top + 2), (x0 + 30, far + 14), (x0 + 90, far - 8), (x0 + 150, far - 2), (x1 - 50, far - 16),
            (x1 - 10, far + 20), (x1 - 2, top + 2)]
    hm = ic.poly_mask(heap)
    ic.fill(hm, GRAVEL, GRAVEL_DK, radial=(x0 + 60, far - 20, 260), noise=0.3)
    pebbles(ic, hm, (x0, far - 20, x1, top + 6), r=(7, 13), density=1.3, scale_y=(0.85, 1))
    ic.outline(heap, 4, (40, 30, 22, 170))
    timber(ic, (x0 + 18, far), (x1 - 18, far), 12, "#8e6844", "#5a3e26")  # far rim
    spill = [(x0 + 50, top - 6), (x0 + 130, top - 8), (x0 + 124, top + 30), (x0 + 96, top + 52), (x0 + 70, top + 26)]
    timber(ic, (x0 - 8, top), (x1 + 8, top), 16, "#b08458", "#6e4c2c")  # front rim
    sm = ic.poly_mask(spill)
    ic.fill(sm, GRAVEL, GRAVEL_DK, (top - 10, top + 50), noise=0.3)
    pebbles(ic, sm, (x0 + 40, top - 10, x0 + 140, top + 56), r=(6, 10), density=1.4, scale_y=(1, 1))
    for _ in range(5):  # pebbles falling down the front
        px, py = x0 + R.uniform(70, 130), top + R.uniform(70, 150)
        r = R.uniform(6, 9)
        ic.ellipse((px - r, py - r * 0.75, px + r, py + r * 0.75), "#b4a48a", "#6a5a44", edge=2)


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    ic.grade["gamma"] = 0.68
    R = ic.random

    # ---- stream across the bottom: darker far edge, ripples, dark wet band against the gravel
    band = ic.water_band(top=780, bottom=878, x0=18, x1=1006, inset=40, sag=30, light=WATER, deep=WATER_DK, surf=False)
    tint(ic, ic.mask("rectangle", (0, 770, SIZE, 806)), band, (22, 44, 54), 0.45, 8)
    tint(ic, ic.mask("ellipse", (620, 820, 960, 880)), band, (230, 242, 244), 0.2, 20)
    ic.overlay(lambda d: [(d.arc((x, y - 10, x + L, y + 10), 200, 340, fill=(232, 244, 246, 200), width=5),
                           d.line([(x + 10, y + 9), (x + L - 10, y + 9)], fill=(20, 50, 62, 110), width=4))
                          for x, y, L in ((640, 822, 70), (760, 846, 60), (900, 820, 56), (700, 880, 80), (860, 874, 64),
                                          (960, 852, 40))], band)

    # ---- gravel bank on the left, running into the water
    bank = [(18, 960), (20, 690), (120, 640), (260, 620), (420, 660), (560, 760), (620, 840), (560, 930), (300, 962)]
    bm = ic.poly_mask(bank)
    ic.fill(bm, GRAVEL, GRAVEL_DK, radial=(80, 620, 640), noise=0.3, chroma=0.12)
    pebbles(ic, bm, (18, 610, 630, 970), r=(8, 16), density=0.9, scale_y=(0.7, 1.05))
    tint(ic, ic.mask("rectangle", (380, 600, 700, 980)), bm, (10, 6, 2), 0.3, 50)
    # wet, dark gravel where the bank meets the stream
    wet = ImageChops.subtract(bm, bm.filter(ImageFilter.MinFilter(41)))
    tint(ic, ic.intersect(wet, ic.mask("rectangle", (440, 700, 700, 980))), bm, (24, 30, 30), 0.55, 10)
    ic.outline(bank, 5, (40, 30, 22, 200))
    ic.shade(ic.poly_mask([(420, 660), (560, 760), (620, 840), (560, 930), (600, 940), (680, 846), (600, 750)]),
             (16, 30, 38), 0.4, blur=10)  # water darkened along the gravel edge
    ic.foam(560, 640, 850)

    # ---- trough on trestles, hopper at the top
    A, B = (200, 452), (850, 616)
    mist(ic, B[0] + 70, B[1] + 190, 230)  # spray behind the trough end
    for t, foot in ((0.16, 700), (0.5, 790), (0.84, 840)):
        trestle(ic, (A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t + 56), foot, 70)
    tm, (ux, uy) = sluice(ic, A, B)
    ic.waterline(ic.mask("rectangle", (560, 700, SIZE, SIZE)), 846)
    spout(ic, B[0] + 6, B[1] - 10, 64, 214, 22)

    # hopper posts, then the funnel box over the head of the trough
    for x in (96, 272):
        timber(ic, (x, 440), (x + 4, 690), 22)
    hopper(ic, 50, 330, 310, 120, 262, 476)
    # feeder launder bringing water in from the top left, trickling into the hopper
    timber(ic, (-4, 196), (150, 250), 30, "#94693f", "#5a3e26")
    ic.line([(2, 190), (146, 244)], 10, "#7c9ea6")
    ic.line([(4, 188), (144, 242)], 4, (236, 246, 246, 200))
    lay, d = layer()
    d.line([(150, 246), (162, 262), (170, 290)], fill=(170, 210, 220, 230), width=14, joint="curve")
    d.line([(150, 246), (162, 262), (170, 290)], fill=(236, 246, 247, 240), width=6, joint="curve")
    ic.image.alpha_composite(lay)

    # ---- sorting table with the stones, basket of gravel, on the bank in front
    table(ic, 110, 430, 812, 76, 952)
    wicker(ic, 440, 590, 872, 960)
