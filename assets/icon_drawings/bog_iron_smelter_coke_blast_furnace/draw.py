"""Coke-Fired Bog Iron Furnace (bog_iron_smelter_coke_blast_furnace): a tall red-brick blast furnace
with a timber charging ramp, a brick blowing house with its own chimney, coke heaps and heavy smoke.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/bog_iron_smelter_coke_blast_furnace/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/bog_iron_smelter_coke_blast_furnace

Tier 2 of the bog iron chain; grows the tier 1 stone stack (bog_iron_smelter_blast_furnace) into a
bigger brick stack. Identity: the tall iron-banded brick stack with a flaming tunnel head and a
thick dark smoke plume, a casting arch pouring glowing iron into a sand pig bed, a brick blowing
house with a tile roof and a smoking engine chimney on the left, grey coke heaps under a timber
charging ramp on the right, reeds and marsh water carried over from tier 1.
Local helpers: as in tier 1 (``stones``, ``tint``, ``union``, ``shingles``, ``planks``, ``smoke``,
``flame``, ``nugget``, ``pile``, ``reeds``, ``cattail``, ``pool``) plus ``bricks`` (from victualling_yard) and ``timber``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 12
REFS = ("bog_iron_smelter", "iron_foundry", "local_smelters", "improved_charcoal_maker")

BASE = 900
IRON = (38, 34, 32)
TIMBER = (112, 78, 50)
# pile colours (lit, dark, glint, shadow), picked before the grade's gamma so they land on target
COKE = ((84, 87, 92), (28, 29, 32), (196, 214, 238), (6, 6, 8))  # coke: porous charcoal-silver
BOG = ((146, 50, 18), (70, 20, 6), (240, 140, 56), (40, 10, 4))  # limonite bog ore: rust red (as tier 1)
BOG_OCHRE = (172, 92, 26)


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


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)


def bricks(ic: Icon, m: Image.Image, box, base="#94604a", dark="#5c3a2c", course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            if ic.random.random() < 0.07:  # over-burnt header
                col = (40, 22, 18, 90)
            else:
                col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    paste_clipped(ic, lay, m)


def timber(ic: Icon, p0, p1, width: float, c1="#86603e", c2="#4e3522") -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def hoop(ic: Icon, y, xl, xr, xs) -> None:
    """Iron band round the stack: across the front, bent back along the side face, anchor plates."""
    ic.line([(xl - 4, y), (xr, y)], 14, (40, 34, 32))
    ic.line([(xr, y), (xs, y - 10)], 14, (26, 22, 20))
    ic.line([(xl - 2, y - 5), (xr, y - 5)], 3, (160, 140, 120, 120))
    for x in (xl + 14, (xl + xr) / 2, xr - 14):
        ic.rect((x - 11, y - 15, x + 11, y + 15), "#56504c", "#242020", edge=3)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.94  # keep the brick and the molten iron warm

    # ---- heavy dark smoke from the tunnel head, lighter smoke from the engine chimney
    smoke(ic, [(962, 128, 50), (900, 88, 62), (812, 66, 74), (720, 70, 72), (646, 92, 60), (590, 112, 44)],
          "#bcb6ae", "#54504c")
    smoke(ic, [(300, 170, 42), (232, 196, 48), (170, 236, 42), (128, 276, 32)], "#dcd8d0", "#88847e")

    # ---- timber charging ramp from the coke yard up to the tunnel head (behind the coke)
    D0, D1 = (640, 212), (984, 534)

    def deck_y(x):
        return D0[1] + (D1[1] - D0[1]) * (x - D0[0]) / (D1[0] - D0[0])

    for x in (776, 872, 962):  # trestle posts; the last one carries the end of the ramp
        timber(ic, (x, deck_y(x) + 8), (x + 4, BASE - 40), 26, "#7e5a3a", "#44301e")
    timber(ic, (780, 700), (872, deck_y(872) + 20), 14, "#7e5a3a", "#44301e")
    timber(ic, (876, 760), (962, deck_y(962) + 20), 14, "#7e5a3a", "#44301e")
    timber(ic, D0, D1, 32, "#94704a", "#5a3e26")
    ic.rect((952, deck_y(962) - 22, 980, deck_y(962) + 26), "#8a6644", "#4a3220", edge=4)  # post head
    ic.line([(652, 166), (970, 466)], 8, (70, 50, 32))  # hand rail
    for x in (720, 840, 962):
        ic.line([(x, deck_y(x) - 46), (x, deck_y(x) - 6)], 7, (70, 50, 32))

    # ---- the stack: tall battered red-brick tower, right side face in shadow
    T = 232
    front = [(318, BASE), (744, BASE), (648, T), (452, T)]
    side = [(744, BASE), (804, 882), (684, T + 12), (648, T)]
    fm, sm = ic.poly_mask(front), ic.poly_mask(side)
    bricks(ic, fm, (300, T, 760, BASE), "#a86448", "#643a2a", course=22, length=48)
    bricks(ic, sm, (640, T, 810, BASE), "#6a3a2a", "#34201a", course=22, length=48)
    tint(ic, ic.mask("rectangle", (300, T - 20, 820, T + 170)), union(fm, sm), (22, 14, 10), 0.6, 44)  # soot
    tint(ic, ic.mask("rectangle", (300, BASE - 120, 820, BASE)), union(fm, sm), (40, 40, 20), 0.25, 26)  # grime
    tint(ic, ic.poly_mask([(570, T), (648, T), (744, BASE), (640, BASE)]), fm, (0, 0, 0), 0.14, 40)
    # stone quoins on the front corners
    for i, y in enumerate(np.arange(T + 10, BASE - 30, 44)):
        t = (y - T) / (BASE - T)
        w = 40 if i % 2 else 26
        xl, xr = 452 - 134 * t, 648 + 96 * t
        ic.poly([(xl + 2, y), (xl + w + 8, y), (xl + w + 8, y + 40), (xl - 2, y + 40)], "#c4b49c", "#8a7c6a", edge=3)
        ic.poly([(xr - w - 8, y), (xr - 2, y), (xr + 2, y + 40), (xr - w - 8, y + 40)], "#a89880", "#6e6252", edge=3)
    for y in (380, 560, 740):
        t = (y - T) / (BASE - T)
        hoop(ic, y, 452 - 134 * t, 648 + 96 * t, 684 + 120 * t)
    ic.outline(front, 5)
    ic.outline(side, 5)

    # ---- tunnel head: narrow brick chimney top with a glowing charging door and flames
    head = ic.mask("rectangle", (474, 132, 626, T))
    bricks(ic, head, (474, 132, 626, T), "#9a5a40", "#4a2a1e", course=20, length=40)
    tint(ic, ic.mask("rectangle", (560, 132, 640, T)), head, (0, 0, 0), 0.3, 16)
    tint(ic, ic.mask("rectangle", (470, 132, 630, 200)), head, (20, 12, 8), 0.4, 20)
    ic.outline([(474, 132), (626, 132), (626, T), (474, T)], 5)
    ic.poly([(440, T - 10), (664, T - 10), (690, T + 14), (420, T + 14)], "#b8a890", "#7a6e60", edge=5)
    ic.poly([(462, 118), (638, 118), (646, 136), (454, 136)], "#b8a890", "#7a6e60", edge=4)
    door = union(ic.mask("ellipse", (604, 160, 640, 196)), ic.mask("rectangle", (604, 178, 640, T - 10)))
    ic.fill(door, "#ffb850", "#c04418", (160, T), noise=0.1)
    for fx, fw, fh, ln in ((-44, 40, 70, -8), (-4, 58, 112, 12), (42, 40, 64, 16)):
        flame(ic, 550 + fx, 124, fw, fh, ln)

    # ---- casting arch at the foot of the stack
    AX0, AX1, ATOP = 464, 604, 626
    AW = AX1 - AX0
    p = 30
    ring = union(ic.mask("ellipse", (AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p)),
                 ic.mask("rectangle", (AX0 - p, ATOP + AW / 2, AX1 + p, BASE)))
    ic.fill(ring, "#c8b8a0", "#807262", (ATOP - p, BASE), noise=0.16)
    ic.overlay(lambda d: d.arc((AX0 - p, ATOP - p, AX1 + p, ATOP + AW + p), 180, 360, fill=(40, 28, 20, 190), width=5))
    opening = union(ic.mask("ellipse", (AX0, ATOP, AX1, ATOP + AW)), ic.mask("rectangle", (AX0, ATOP + AW / 2, AX1, BASE)))
    with ic.clipped(opening):
        ic.fill(opening, "#2a160c", "#0c0604", (ATOP, BASE), noise=0.12)
        tint(ic, ic.mask("ellipse", (AX0 - 40, 730, AX1 + 40, 980)), None, (255, 130, 40), 0.95, 24)
        ic.fill(ic.mask("ellipse", (AX0 + 12, 836, AX1 - 12, 904)), "#fff4c0", "#ff9a30", (836, 904), noise=0.08)
    tint(ic, ic.mask("ellipse", (AX0 - 150, 690, AX1 + 150, 1010)), union(ring, fm), (255, 140, 50), 0.34, 30)

    # ---- blowing house (left): brick, tile roof, engine chimney, blast pipe into the stack
    HX0, HX1, HEAVE, HRIDGE = 20, 344, 650, 520
    ch = ic.mask("rectangle", (74, 290, 146, 560))
    bricks(ic, ch, (74, 290, 146, 560), "#9a5a40", "#4e2e22", course=18, length=36)
    tint(ic, ic.mask("rectangle", (116, 290, 160, 560)), ch, (0, 0, 0), 0.3, 10)
    tint(ic, ic.mask("rectangle", (70, 290, 150, 340)), ch, (20, 12, 8), 0.4, 14)
    ic.outline([(74, 290), (146, 290), (146, 560), (74, 560)], 5)
    ic.poly([(62, 276), (158, 276), (158, 298), (62, 298)], "#b8a890", "#7a6e60", edge=4)
    wall = ic.mask("rectangle", (HX0 + 14, HEAVE, HX1 - 10, BASE))
    bricks(ic, wall, (HX0 + 14, HEAVE, HX1 - 10, BASE), "#a0624a", "#5a3628", course=20, length=44)
    tint(ic, ic.mask("rectangle", (HX1 - 90, HEAVE, HX1, BASE)), wall, (0, 0, 0), 0.25, 30)
    tint(ic, ic.mask("rectangle", (HX0, BASE - 80, HX1, BASE)), wall, (40, 40, 20), 0.25, 20)
    ic.outline([(HX0 + 14, HEAVE), (HX1 - 10, HEAVE), (HX1 - 10, BASE), (HX0 + 14, BASE)], 5)
    roof = [(HX0 + 40, HRIDGE), (HX1 - 30, HRIDGE), (HX1 + 14, HEAVE + 6), (HX0 - 16, HEAVE + 6)]
    rm = shingles(ic, roof, "#827a70", "#3e3834", course=26, stagger=34, edge=6)
    tint(ic, ic.poly_mask([(HX1 - 120, HRIDGE), (HX1 + 20, HRIDGE), (HX1 + 20, HEAVE + 8), (HX1 - 80, HEAVE + 8)]), rm,
         (0, 0, 0), 0.25, 30)
    ic.poly([(HX0 + 36, HRIDGE - 12), (HX1 - 26, HRIDGE - 12), (HX1 - 26, HRIDGE + 6), (HX0 + 36, HRIDGE + 6)],
            "#6e6660", "#44403c", edge=4)
    tint(ic, ic.mask("rectangle", (HX0, HEAVE + 6, HX1, HEAVE + 50)), wall, (0, 0, 0), 0.42, 12)
    ic.window(62, 716, 104, 772)
    # large arched engine doorway, dark inside with the blowing engine's flywheel just visible
    DX0, DX1, DTOP = 160, 286, 704
    DW = DX1 - DX0
    pad = 20
    surround = union(ic.mask("ellipse", (DX0 - pad, DTOP - pad, DX1 + pad, DTOP + DW + pad)),
                     ic.mask("rectangle", (DX0 - pad, DTOP + DW / 2, DX1 + pad, BASE)))
    ic.fill(surround, "#bca88c", "#7a6a58", (DTOP - pad, BASE), noise=0.16)
    hole = union(ic.mask("ellipse", (DX0, DTOP, DX1, DTOP + DW)), ic.mask("rectangle", (DX0, DTOP + DW / 2, DX1, BASE)))
    with ic.clipped(hole):
        ic.fill(hole, "#2a1e18", "#0a0706", (DTOP, BASE), noise=0.12)
        wx, wy, wr = 236, 812, 62
        ic.overlay(lambda d: d.ellipse((wx - wr, wy - wr, wx + wr, wy + wr), outline=(96, 86, 78, 230), width=12))
        for a in range(0, 180, 45):
            dx, dy = math.cos(math.radians(a)) * wr, math.sin(math.radians(a)) * wr
            ic.line([(wx - dx, wy - dy), (wx + dx, wy + dy)], 6, (80, 72, 66, 210))
        ic.line([(DX0, 752), (DX1, 730)], 14, (84, 60, 40, 230))  # engine beam
        tint(ic, ic.mask("rectangle", (DX0, DTOP, DX1, DTOP + 60)), None, (0, 0, 0), 0.6, 20)
    ic.overlay(lambda d: d.arc((DX0, DTOP, DX1, DTOP + DW), 180, 360, fill=(40, 28, 20, 220), width=5))
    ic.line([(DX0, DTOP + DW / 2), (DX0, BASE)], 5, (40, 28, 20, 220))
    ic.line([(DX1, DTOP + DW / 2), (DX1, BASE)], 5, (40, 28, 20, 220))
    # blast pipe from the blowing house into the stack, entering above the casting arch
    pipe = [(HX1 - 20, 742), (398, 742), (462, 604)]
    ic.line(pipe, 50, (16, 14, 12))
    ic.line(pipe, 38, (50, 46, 44))
    ic.line([(HX1 - 20, 732), (392, 732), (452, 604)], 7, (132, 124, 116, 150))
    for (x, y), ang in (((HX1 - 4, 742), 0), ((398, 742), 30), ((456, 618), -65)):
        pts = ic.rotate([(-9, -32), (9, -32), (9, 32), (-9, 32)], (x, y), ang)
        ic.poly(pts, "#56504c", "#1e1c1c", edge=3)

    # ---- marsh ground, pool, sand pig bed with glowing runners
    ground = [(8, 952), (24, 896), (1000, 896), (1016, 954)]
    ic.poly(ground, "#655a3a", "#3a3222", noise=0.3)
    pool(ic, [(8, 950), (30, 912), (170, 906), (250, 918), (220, 956), (50, 962)])
    # sand pig bed spreading out from the casting arch: a thick glowing runner with stubby moulds
    bed = [(404, 898), (668, 898), (742, 976), (332, 976)]
    ic.poly(bed, "#86694c", "#4a3a2a", noise=0.25, edge=0)
    tint(ic, ic.poly_mask([(332, 950), (742, 950), (742, 980), (332, 980)]), ic.poly_mask(bed), (40, 26, 14), 0.35, 10)
    ic.outline(bed, 7, (58, 38, 22))
    runs = [[(534, 896), (534, 934)], [(392, 938), (694, 942)]]
    runs += [[(x, 942), (x + 2, 964)] for x in (446, 608, 662)]
    for w, col in ((44, (54, 22, 10)), (32, (214, 84, 22)), (16, (255, 150, 52)), (5, (255, 230, 160))):
        for r in runs:
            ic.line(r, w, col)
    tint(ic, ic.poly_mask(bed), None, (255, 120, 40), 0.14, 22)

    # ---- coke heap bottom right: low mound of porous charcoal-silver lumps
    pile(ic, 704, 992, 962, 668, 28, 8, COKE, ("#1a1a1c", "#08080a"), knob=0.12, pores=14, peak=0.5)
    # ---- rusty bog ore (as tier 1) at the foot of the stack
    pile(ic, 222, 392, 962, 846, 24, 4, BOG, ("#4a1a0a", "#1e0a04"), knob=0.22, pores=2, peak=0.3, alt=BOG_OCHRE)

    # ---- reeds; the right-hand clump bends inwards so the outline wraps round it
    reeds(ic, 30, 950, 60, 210, 9)
    reeds(ic, 212, 948, 30, 120, 5, tails=1)
    reeds(ic, 966, 950, 30, 160, 7, lean_bias=-0.25)
