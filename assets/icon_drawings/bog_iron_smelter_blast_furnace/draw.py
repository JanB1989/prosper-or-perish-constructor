"""Bog Iron Blast Furnace (bog_iron_smelter_blast_furnace): squat stone blast-furnace stack with a
bellows house, charcoal and bog ore, standing in marsh reeds.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/bog_iron_smelter_blast_furnace/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/bog_iron_smelter_blast_furnace

Tier 1 of the bog iron chain (the base Bog Iron Smelter keeps the vanilla clay beehive kiln).
Identity: a battered rubble-stone stack with a glowing charging mouth and a glowing tapping arch, a
timber bellows house on its left whose open front shows a big leather wedge bellows blowing into the
stack, a black charcoal heap bottom right, a pile of rusty bog ore bottom left, reeds and a marsh
pool for the wetland. Tier 2 (coke) grows this into a tall brick stack with coke heaps.
Local helpers: ``stones``, ``tint``, ``union``, ``shingles``, ``planks``, ``smoke``, ``flame``
(from cookshop/tavern), new ``reeds`` + ``cattail``, ``nugget`` (rounded knobbly lump shaded as a form), ``pile`` (mound of
nuggets over a dark body), ``pool``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("bog_iron_smelter", "schwaz_mine", "local_smelters", "charcoal_maker")

BASE = 900
IRON = (38, 34, 32)
TIMBER = (112, 78, 50)
# pile colours (lit, dark, glint, shadow), picked before the grade's gamma so they land on target
CHAR = ((58, 56, 58), (8, 8, 10), (120, 150, 200), (0, 0, 2))  # charcoal: black with a bluish sheen
BOG = ((146, 50, 18), (70, 20, 6), (240, 140, 56), (40, 10, 4))  # limonite bog ore: rust red
BOG_OCHRE = (172, 92, 26)  # every third lump or so is yellower ochre


# ---------------------------------------------------------------- helpers
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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form: tone variation, lit top-left edge, shadowed bottom-right."""
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
            w = course * rnd(1.1, 2.3)
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
    """Roof plane of overlapping shingles with per-tile tone and course shadows; returns the mask."""
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


def smoke(ic: Icon, puffs, light="#e8e4dc", dark="#8e8a84") -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, light, dark, radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#ffbe55", "#c9451c"), inner=("#fff3c4", "#ffb449")) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (inner, 0.5, 0.62)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def _rgb(c):
    if isinstance(c, str):
        return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return c[:3]


def nugget(ic: Icon, cx, cy, r, c1, c2, glint, shadow, knob=0.13, pores=0, glint_alpha=0.55) -> None:
    """One rounded, knobbly lump shaded as a form: lit top-left, core shadow bottom-right, a small
    highlight, optional dark pore dots (coke)."""
    R = ic.random
    ph = [R.uniform(0, 2 * math.pi) for _ in range(3)]
    k1, k2 = R.randint(2, 3), R.randint(4, 6)
    sq = R.uniform(0.72, 0.9)
    pts = [(cx + math.cos(a) * r * kk, cy + math.sin(a) * r * sq * kk)
           for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)
           for kk in [1 + knob * math.sin(k1 * a + ph[0]) + knob * 0.6 * math.sin(k2 * a + ph[1])]]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, radial=(cx - r * 0.5, cy - r * 0.55, r * 2.0), noise=0.22, chroma=0.05)
    tint(ic, ic.mask("ellipse", (cx - r * 0.1, cy, cx + r * 1.3, cy + r * 1.2)), m, shadow, 0.5, r * 0.25)
    if pores:
        lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for _ in range(pores):
            px, py = cx + R.uniform(-0.7, 0.7) * r, cy + R.uniform(-0.55, 0.55) * r
            pr = r * R.uniform(0.05, 0.09)
            d.ellipse((px - pr, py - pr * 0.8, px + pr, py + pr * 0.8), fill=(8, 8, 10, 160))
        clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), m)
        ic.image.alpha_composite(clip)
    hx, hy = cx - r * 0.38, cy - r * 0.38
    tint(ic, ic.mask("ellipse", (hx - r * 0.26, hy - r * 0.16, hx + r * 0.26, hy + r * 0.16)), m, glint,
         glint_alpha, r * 0.08)
    ic.outline(pts, 3, tuple(shadow) + (200,))


def pile(ic: Icon, x0, x1, base, top, r, rows, colors, body, knob=0.13, pores=0, peak=0.5, alt=None) -> None:
    """Mound of rounded lumps over a dark body; the body shows as dark gaps between the lumps.

    ``colors`` = (lit, dark, glint, shadow); ``peak`` 0 = round dome, 1 = pointed cone."""
    c1, c2, glint, shadow = colors
    cx = (x0 + x1) / 2
    outline = []
    for a in np.linspace(math.pi, 0, 24):
        u = math.cos(a)  # -1..1 across
        dome = math.sin(a)
        cone = 1 - abs(u)
        h = dome * (1 - peak) + cone * peak
        outline.append((cx + u * (x1 - x0) / 2, base - (base - top) * h))
    ic.poly(outline, body[0], body[1], noise=0.3, edge=4)
    R = ic.random
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.6 + (base - top - r * 0.9) * t
        h = (base - y) / (base - top)
        half = (x1 - x0) / 2 * min(1.0, (1 - h) * 0.95 + 0.12) - r * 0.4
        half = max(half, r * 0.3)
        n = max(1, int(round(2 * half / (r * 1.35))))
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + R.uniform(-8, 8)
            k = R.uniform(0.85, 1.12)
            src = alt if alt is not None and R.random() < 0.35 else c1
            lit = tuple(int(min(255, v * k)) for v in _rgb(src))
            nugget(ic, x, y + R.uniform(-5, 5), r * R.uniform(0.8, 1.12), lit, c2, glint, shadow, knob, pores)
    ic.shade(ic.poly_mask([(cx + r, top), (x1 + 20, base - 40), (x1 + 20, base + 10), (cx + r, base + 10)]),
             (0, 0, 0), 0.22, blur=30)


def cattail(ic: Icon, bx, base, h, lean) -> None:
    """Cattail: its own thin stalk up to a rounded brown head with a short spike."""
    ts = np.linspace(0, 1, 10)
    stalk = [(bx + lean * t * t, base - h * t) for t in ts]
    ic.line(stalk, 6, (88, 96, 48))
    tx, ty = stalk[-1]
    ic.ellipse((tx - 9, ty - 44, tx + 9, ty + 4), "#86583a", "#3e2616", edge=3)
    ic.shade(ic.mask("ellipse", (tx - 7, ty - 40, tx - 1, ty - 10)), (255, 220, 170), 0.25, blur=2)
    ic.line([(tx, ty - 44), (tx + lean * 0.02, ty - 64)], 4, (70, 58, 36))


def reeds(ic: Icon, x, base, w, h, n=14, lean_bias=0.0, tails=2) -> None:
    """Clump of marsh reeds: tapering blades, some bent, a few cattails on their own stalks.

    ``lean_bias`` < 0 bends the clump to the left (use at the right edge so the outline wraps round)."""
    R = ic.random
    blades = []
    for _ in range(n):
        bx = x + R.uniform(-w / 2, w / 2)
        bh = h * R.uniform(0.55, 1.0)
        lean = (R.uniform(-0.35, 0.35) + lean_bias) * bh
        blades.append((bx, bh, lean))
    blades.sort(key=lambda b: -b[1])
    for bx, bh, lean in blades:
        ts = np.linspace(0, 1, 12)
        bw = R.uniform(9, 14)
        spine = [(bx + lean * t * t, base - bh * t) for t in ts]
        left = [(sx - bw / 2 * (1 - t), sy) for (sx, sy), t in zip(spine, ts)]
        right = [(sx + bw / 2 * (1 - t), sy) for (sx, sy), t in zip(spine, ts)]
        pts = left + right[::-1]
        g = R.uniform(0.8, 1.15)
        c1 = tuple(int(v * g) for v in (132, 142, 72))
        c2 = tuple(int(v * g) for v in (58, 70, 32))
        ic.fill(ic.poly_mask(pts), c1, c2, (base, base - bh), noise=0.2)
        ic.shade(ic.poly_mask(right[:1] + spine + right[::-1]), (10, 16, 4), 0.3)
    for bx, bh, lean in blades[1:1 + tails]:
        cattail(ic, bx + R.uniform(-6, 6), base, bh * R.uniform(0.8, 0.95), lean * 0.4)


def pool(ic: Icon, pts) -> Image.Image:
    """Still marsh water: dark peaty surface, lighter far edge, a few sky glints."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, "#6a8a8c", "#2a3a38", (min(ys), max(ys)), noise=0.1)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    xs = [p[0] for p in pts]
    for _ in range(10):
        y = ic.random.uniform(min(ys) + 8, max(ys) - 6)
        x = ic.random.uniform(min(xs), max(xs))
        L = ic.random.uniform(30, 80)
        d.line([(x, y), (x + L, y)], fill=(210, 226, 222, 120), width=4)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    ic.outline(pts, 4)
    return m


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.96  # keep the furnace glow and the leather warm

    # ---- smoke from the charging mouth, drifting right
    smoke(ic, [(850, 70, 44), (776, 88, 58), (700, 120, 62), (628, 164, 54), (570, 206, 42)])

    # ---- the stack: massive battered rubble-stone tower, right side face in shadow
    T = 262  # top of the stack
    front = [(326, BASE), (720, BASE), (630, T), (424, T)]
    side = [(720, BASE), (778, 880), (668, T + 12), (630, T)]
    fm, sm = ic.poly_mask(front), ic.poly_mask(side)
    stones(ic, (320, T, 730, BASE), "#b8946e", "#654a36", course=42, clip=fm)
    stones(ic, (620, T, 780, BASE), "#735c48", "#3a2c22", course=42, clip=sm, lit=30, shadow=110)
    stack = union(fm, sm)
    tint(ic, ic.mask("rectangle", (300, T - 20, 800, T + 170)), stack, (22, 14, 8), 0.62, 44)  # soot at the top
    tint(ic, ic.mask("rectangle", (300, BASE - 110, 800, BASE)), stack, (44, 40, 20), 0.22, 26)  # grime
    tint(ic, ic.poly_mask([(560, T), (630, T), (720, BASE), (620, BASE)]), fm, (0, 0, 0), 0.14, 40)
    tint(ic, ic.mask("ellipse", (380, 600, 680, 960)), fm, (24, 14, 8), 0.5, 34)  # soot round the arch
    # rust stains running down from the tie bars
    R = ic.random
    for y in (470, 660):
        t = (y - T) / (BASE - T)
        xl, xr = 424 - 98 * t, 630 + 90 * t
        for _ in range(7):
            sx = R.uniform(xl + 10, xr - 10)
            sw, sl = R.uniform(10, 22), R.uniform(50, 120)
            streak = [(sx - sw / 2, y + 6), (sx + sw / 2, y + 6), (sx + sw * 0.2, y + sl), (sx - sw * 0.2, y + sl)]
            tint(ic, ic.poly_mask(streak), fm, (130, 52, 18), R.uniform(0.3, 0.5), 7)
    # iron tie bars with anchor plates
    for y in (470, 660):
        t = (y - T) / (BASE - T)
        xl, xr = 424 - 98 * t, 630 + 90 * t
        ic.line([(xl - 4, y), (xr, y)], 13, (44, 36, 32))
        ic.line([(xr, y), (xr + 58 * t + 12, y - 8)], 13, (30, 26, 24))
        ic.line([(xl - 2, y - 4), (xr, y - 4)], 3, (150, 130, 110, 110))
        for x in (xl + 12, xr - 12):
            ic.rect((x - 12, y - 16, x + 12, y + 16), "#56504c", "#242020", edge=3)
    ic.outline(front, 5)
    ic.outline(side, 5)
    # crown and glowing charging mouth
    ic.poly([(410, T - 22), (646, T - 22), (682, T + 12), (396, T + 12)], "#b89c7c", "#5e4c3c", edge=5)
    ic.fill(ic.mask("ellipse", (456, T - 40, 614, T - 2)), "#ffc864", "#b8401a", (T - 40, T - 2), noise=0.1)
    for fx, fw, fh, ln in ((-46, 36, 56, -8), (0, 50, 88, 10), (44, 36, 50, 14)):
        flame(ic, 535 + fx, T - 16, fw, fh, ln)

    # ---- tapping arch at the foot of the stack, glowing hearth inside
    AX0, AX1, ATOP = 470, 590, 664
    AW = AX1 - AX0
    p = 28
    ring = union(ic.mask("ellipse", (AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p)),
                 ic.mask("rectangle", (AX0 - p, ATOP + AW / 2, AX1 + p, BASE)))
    ic.fill(ring, "#c0a282", "#6e5a48", (ATOP - p, BASE), noise=0.16)
    tint(ic, ic.mask("ellipse", (AX0 - p - 10, ATOP - p - 20, AX1 + p + 10, ATOP + 50)), ring, (24, 14, 8), 0.45, 16)
    ic.overlay(lambda d: d.arc((AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p), 180, 360, fill=(40, 28, 20, 190), width=5))
    opening = union(ic.mask("ellipse", (AX0, ATOP, AX1, ATOP + AW)), ic.mask("rectangle", (AX0, ATOP + AW / 2, AX1, BASE)))
    with ic.clipped(opening):
        ic.fill(opening, "#2a160c", "#0c0604", (ATOP, BASE), noise=0.12)
        tint(ic, ic.mask("ellipse", (AX0 - 40, 760, AX1 + 40, 960)), None, (255, 130, 40), 0.9, 24)
        ic.fill(ic.mask("ellipse", (AX0 + 10, 846, AX1 - 10, 902)), "#fff0b0", "#ff9a30", (846, 902), noise=0.08)
    tint(ic, ic.mask("ellipse", (AX0 - 130, 720, AX1 + 130, 1000)), union(ring, fm), (255, 140, 50), 0.32, 30)

    # ---- bellows house (left): pent shingle roof against the stack, open front, dark inside
    HX0, HX1, HTOP, HEAVE = 30, 420, 560, 646
    back = ic.mask("rectangle", (HX0, HTOP, HX1, BASE))
    planks(ic, (HX0, HTOP, HX1, BASE), "#5e4a36", "#2e2218", board=34, clip=back)
    tint(ic, ic.mask("rectangle", (HX0, HEAVE, HX1, BASE)), back, (10, 6, 4), 0.72, 20)
    # the bellows: a big leather wedge, boards meeting at the iron nozzle
    top_b = [(96, 700), (392, 780)]
    bot_b = [(96, 872), (392, 816)]
    # leather body: pleats bulge out behind the boards as a row of chevron folds
    folds = np.linspace(0.0, 0.86, 7)

    def edge_pt(f, which):
        (xa, ya), (xb, yb) = top_b if which == 0 else bot_b
        return (xa + (xb - xa) * f, ya + (yb - ya) * f)

    mid = lambda f: ((edge_pt(f, 0)[0] + edge_pt(f, 1)[0]) / 2 - 34 * (1 - f),  # noqa: E731
                     (edge_pt(f, 0)[1] + edge_pt(f, 1)[1]) / 2)
    leather = [edge_pt(0, 0), top_b[1], bot_b[1], edge_pt(0, 1), (40, 786)]
    lm = ic.poly_mask(leather)
    ic.fill(lm, "#9a5a32", "#3c1e0e", radial=(90, 720, 380), noise=0.16)
    for i, f in enumerate(folds):
        chev = [edge_pt(f, 0), mid(f), edge_pt(f, 1)]
        nxt = min(f + 0.07, 1)
        band = chev + [edge_pt(nxt, 1), mid(nxt), edge_pt(nxt, 0)]
        ic.shade(ic.intersect(ic.poly_mask(band), lm), (255, 214, 160), 0.30, blur=3)
        ic.line(chev, 6, (28, 12, 4, 210))
    ic.outline(leather, 5)
    for (a, b) in (top_b, bot_b):
        ic.beam(a, b, 26, (150, 104, 62))
        for f in (0.2, 0.5, 0.8):
            x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            ic.draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(40, 36, 34, 255))
    ic.poly([(86, 684), (110, 684), (110, 888), (86, 888)], "#9a6c44", "#4e3420", edge=4)  # back board
    ic.poly([(386, 774), (430, 786), (430, 808), (386, 822)], "#5a5654", "#2a2826", edge=4)  # iron nozzle
    ic.line([(170, 712), (182, HEAVE)], 12, IRON)  # rocker rod up to the roof beam
    ic.shade(ic.mask("ellipse", (70, 860, 420, 940)), (0, 0, 0), 0.35, blur=18)
    # posts and roof
    for x0, x1 in ((HX0 + 12, HX0 + 16), (HX1 - 10, HX1 - 12)):
        ic.beam((x0, HEAVE), (x1, BASE), 26, TIMBER)
    roof = [(HX0 + 34, HTOP), (HX1 + 10, HTOP - 8), (HX1 + 24, HEAVE), (HX0 - 26, HEAVE + 8)]
    rm = shingles(ic, roof, "#9a8266", "#54443a", course=26, stagger=34, edge=6)
    tint(ic, ic.poly_mask([(HX1 - 90, HTOP - 10), (HX1 + 30, HTOP - 10), (HX1 + 30, HEAVE), (HX1 - 60, HEAVE)]), rm,
         (0, 0, 0), 0.22, 30)
    ic.beam((HX0 - 26, HEAVE + 10), (HX1 + 24, HEAVE + 2), 24, (110, 76, 48))
    tint(ic, ic.mask("rectangle", (HX0, HEAVE + 14, HX1, HEAVE + 70)), back, (0, 0, 0), 0.45, 14)

    # ---- marsh ground: a peaty strip and a pool in front of the bellows house
    ground = [(10, 950), (30, 896), (984, 896), (1000, 948)]
    ic.poly(ground, "#655a3a", "#3a3222", noise=0.3)
    water = [(6, 962), (22, 912), (300, 902), (452, 914), (432, 956), (220, 970)]
    wm = pool(ic, water)

    # ---- charcoal heap bottom right: big, black, bluish sheen
    pile(ic, 690, 990, 944, 640, 40, 7, CHAR, ("#141212", "#040404"), knob=0.2, peak=0.55)
    # wicker basket heaped with charcoal in front of the heap, a dark gap between them
    ic.shade(ic.mask("rectangle", (748, 800, 944, 980)), (0, 0, 0), 0.85, blur=14)
    ic.basket(766, 846, 914, 962, colors=("#b88e56", "#6a4a28"))
    with ic.clipped(ic.mask("rectangle", (0, 0, ic.size, 852))):
        ic.ellipse((774, 812, 906, 866), "#141212", "#050505", edge=0)
        for x, y, r in ((792, 838, 22), (820, 820, 25), (854, 808, 27), (888, 826, 23), (808, 846, 21),
                        (842, 840, 23), (876, 846, 21), (900, 846, 17)):
            nugget(ic, x, y, r, *CHAR, knob=0.2)
    ic.line([(766, 848), (914, 848)], 9, (70, 48, 26))  # basket rim

    # ---- bog ore dug from the marsh: rusty knobbly lumps sitting in the pool
    pile(ic, 16, 312, 958, 786, 29, 6, BOG, ("#4a1a0a", "#1e0a04"), knob=0.22, pores=3, peak=0.3, alt=BOG_OCHRE)
    # water laps round the foot of the pile (repaint the pool over everything below the waterline)
    lap_pts = [(8, 942), (330, 942), (330, 962), (220, 974), (8, 966)]
    ic.image.paste((0, 0, 0, 0), (0, 942, 330, 1024))
    ic.fill(ic.poly_mask(lap_pts), "#50686a", "#26343a", (942, 974), noise=0.1)
    ic.overlay(lambda d: [d.line([(x, 947 + (x % 7)), (x + 34, 947 + (x % 7))], fill=(210, 226, 222, 140), width=4)
                          for x in (34, 118, 196, 262)])
    ic.line([(14, 942), (326, 942)], 4, (30, 40, 38, 190))
    ic.line(lap_pts[1:] + [lap_pts[0]], 4)
    # hot iron runnel from the arch into a sand bed
    ic.line([(530, 904), (566, 922), (640, 930)], 16, (255, 150, 50))
    ic.line([(530, 904), (566, 922), (640, 930)], 6, (255, 236, 170))

    # ---- reeds; the right-hand clump bends inwards so the outline wraps round it
    reeds(ic, 340, 958, 50, 180, 8)
    reeds(ic, 452, 950, 40, 130, 6, tails=1)
    reeds(ic, 962, 944, 30, 170, 7, lean_bias=-0.25)
