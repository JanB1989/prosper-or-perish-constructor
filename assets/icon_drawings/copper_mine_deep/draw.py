"""Deep Copper Works (copper_mine_deep): a tall headframe over a stone shaft beside a coal-fired
reverberatory furnace with a brick chimney.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor-stockpile-prices/assets/icon_drawings/copper_mine_deep/draw.py \
    --out ../ProsperOrPerishConstructor-stockpile-prices/artifacts/icons/copper_mine_deep

Composition: top tier of the copper chain (Copper Mine -> Adit Copper Mine -> Deep Copper Works). The
malachite-crusted tan rock of the family is now only a backdrop on the left. A braced timber headframe
with a big sheave rises over a stone shaft collar; right of it a low brick furnace vault with iron
buckstays and a glowing door feeds a tall tapering chimney. In front a mine tub heaped with green and
copper-red ore, a broad ore mound bottom left and a stack of finished copper cakes bottom right, which
carry the colour and show the bigger output. Local helpers: ``crust``, ``mound``, ``ore_lumps``
(copper_mine_adit), ``tub``, ``wheel``, ``headframe`` (iron_mine_deep), ``bricks``, ``smoke``, ``tint``,
``union`` (lead_mine_cupola_smelting), ``cake``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 29
REFS = ("schwaz_mine", "iron_foundry", "stone_quarry", "steel_mill")

SIZE = 1024
ROCK = "#b89e78"
ROCK_DARK = "#4f3f30"
MAL = "#5ea888"  # malachite, lit
MAL_DARK = "#1c4a3a"
MAL_EDGE = (14, 40, 30)
CU = "#c86f3e"  # native copper / cuprite, lit
CU_DARK = "#5a2614"
TIMBER = (112, 76, 48)
TIMBER_LIT = (146, 102, 64)
POST = (120, 82, 52)
BRACE = (98, 66, 42)
IRON = (46, 44, 46)
DARK = (28, 18, 12)
BRICK = ("#a4644a", "#5a3224")


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


def ore_lumps(ic: Icon, pts, r: float, share_cu: float = 0.3) -> None:
    for x, y in pts:
        rr = r * ic.random.uniform(0.8, 1.15)
        if ic.random.random() < share_cu:
            ic.chunk(x, y, rr, CU, CU_DARK, (255, 200, 150))
        else:
            ic.chunk(x, y, rr, MAL, MAL_DARK, (210, 255, 225))


def crust(ic: Icon, path, depth: float, c1=MAL, c2=MAL_DARK, edge=MAL_EDGE, specks: int = 7) -> None:
    """Malachite crust lying on a ledge or facet (same as copper_mine_adit)."""
    rng = np.random.default_rng(ic.random.randint(0, 2 ** 31))
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    ends = np.concatenate([[0], np.cumsum(seg)])
    n = max(10, int(ends[-1] / 12))
    d = np.linspace(0, ends[-1], n)
    xs, ys = np.interp(d, ends, pts[:, 0]), np.interp(d, ends, pts[:, 1])
    tx, ty = np.gradient(xs), np.gradient(ys)
    ln = np.hypot(tx, ty) + 1e-6
    nx, ny = -ty / ln, tx / ln
    flip = np.where(ny < 0, -1.0, 1.0)
    nx, ny = nx * flip, ny * flip
    prof = np.sin(np.pi * np.linspace(0.04, 0.96, n)) ** 0.5
    wob = np.convolve(rng.uniform(0.2, 1.4, n + 4), np.ones(5) / 5, "valid")[:n]
    th = depth * 1.2 * prof * wob
    top = [(x - a * 4 + rng.uniform(-3, 3), y - b * 4 + rng.uniform(-3, 3)) for x, y, a, b in zip(xs, ys, nx, ny)]
    bot = [(x + a * t + rng.uniform(-7, 7), y + b * t + rng.uniform(-5, 5))
           for x, y, a, b, t in zip(xs, ys, nx, ny, th)]
    m = ic.poly_mask(top + bot[::-1])
    for _ in range(3):
        k = rng.integers(0, n)
        cx, cy = xs[k] + nx[k] * (th[k] + 14), ys[k] + ny[k] * (th[k] + 14)
        r = rng.uniform(8, 16)
        m = ImageChops.lighter(m, ic.poly_mask(ic.jitter(cx, cy, r * 1.4, r, 7, 0.3)))
    holes = Image.fromarray((rng.random((30, 30)) * 255).astype("uint8")).resize((SIZE, SIZE), Image.BICUBIC)
    holes = holes.point(lambda v: 255 if v > 62 else 0)
    m = ImageChops.multiply(m, holes).filter(ImageFilter.MedianFilter(5))
    lo, hi = float(min(ys.min(), (ys + ny * th).min())), float(max(ys.max(), (ys + ny * th).max()))
    under = ImageChops.subtract(ImageChops.offset(m, 0, 7), m)
    ic.shade(under, (30, 22, 16), 0.35, blur=2)
    ic.fill(m, c1, c2, (lo - 6, hi + 10), noise=0.45)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, 0, -10)), edge, 0.7)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, 0, 6)), (205, 245, 220), 0.3)
    for _ in range(specks):
        k = rng.integers(0, n)
        s = rng.uniform(-0.4, 1.8)
        cx = xs[k] + nx[k] * th[k] * s + rng.uniform(-18, 18)
        cy = ys[k] + ny[k] * th[k] * s + rng.uniform(-10, 14)
        r = rng.uniform(4, 8)
        ic.shade(ic.poly_mask(ic.jitter(cx, cy, r, r * 0.8, 6, 0.25)), (84, 160, 124), 0.8)


def mound(ic: Icon, x0, x1, base, top, r, rows, cu_share=0.4, body=("#3f5a48", "#1d2b22"), power=0.65) -> None:
    """Rounded ore heap: a domed body with rows of lumps and a soft lit crown (from copper_mine_adit)."""
    ts = np.linspace(0, 1, 28)
    outline = [(x0 + (x1 - x0) * t, base - (base - top) * np.sin(np.pi * t) ** power) for t in ts]
    ic.poly(outline, body[0], body[1], noise=0.3)
    crown = [(x0 + (x1 - x0) * t, base - (base - top + r * 0.5) * np.sin(np.pi * t) ** power) for t in ts]
    with ic.clipped(ic.poly_mask(crown + [(x1 + r, base + r), (x0 - r, base + r)])):
        for i in range(rows):
            t = i / max(rows - 1, 1)
            y = top + r * 0.55 + (base - top - r * 0.9) * t
            h = np.clip((base - y) / (base - top), 0, 1)
            tt = np.arcsin(h ** (1 / power)) / np.pi
            half = (x1 - x0) * (0.5 - tt) - r * 0.35
            n = max(1, int(2 * half / (r * 1.25)) + 1)
            cx = (x0 + x1) / 2
            for j in range(n):
                x = cx - half + (j + 0.5) * 2 * half / n + ic.random.uniform(-10, 10)
                rr = r * ic.random.uniform(0.8, 1.1)
                if ic.random.random() < cu_share:
                    ic.chunk(x, y, rr, CU, CU_DARK, (255, 200, 150))
                else:
                    ic.chunk(x, y, rr, MAL, MAL_DARK, (210, 255, 225))
    m = ic.poly_mask(outline)
    ic.shade(ic.poly_mask([(x0 + (x1 - x0) * 0.55, top), (x1 + 20, top), (x1 + 20, base), (x0 + (x1 - x0) * 0.62, base)]),
             alpha=0.28, blur=24)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (x0 + (x1 - x0) * 0.15, top - 20, x0 + (x1 - x0) * 0.6, top + (base - top) * 0.5))),
             (255, 240, 220), 0.12, blur=20)


def tub(ic: Icon, x0: float, x1: float, top: float, bot: float) -> None:
    """Plank mine tub heaped with green and copper-red ore, iron-banded, on two small wheels (from iron_mine_deep)."""
    w = x1 - x0
    ore_lumps(ic, [(x0 + w * 0.16, top - 10), (x0 + w * 0.45, top - 32), (x0 + w * 0.76, top - 14),
                   (x0 + w * 0.30, top + 4), (x0 + w * 0.60, top + 2)], 44, 0.4)
    body = [(x0, top), (x1, top), (x1 - w * 0.07, bot), (x0 + w * 0.07, bot)]
    ic.poly(body, "#9a6a44", "#523620", noise=0.25)
    for f in (0.36, 0.68):
        y = top + (bot - top) * f
        ic.line([(x0 + w * 0.07 * f, y), (x1 - w * 0.07 * f, y)], 4, (58, 38, 22, 200))
    for fx in (0.14, 0.86):
        x = x0 + w * fx
        ic.line([(x, top + 2), (x + (0.5 - fx) * w * 0.07, bot - 2)], 12, IRON)
    ic.shade(ic.poly_mask([body[0], body[1], (x1 - 3, top + 14), (x0 + 3, top + 14)]), (255, 235, 210), 0.25)
    for cx in (x0 + w * 0.24, x1 - w * 0.24):
        ic.ellipse((cx - 34, bot - 22, cx + 34, bot + 44), "#4c4a4c", "#1e1c1e", edge=5)
        ic.ellipse((cx - 9, bot + 2, cx + 9, bot + 20), "#7a7274", "#3a3638", edge=3)


def wheel(ic: Icon, cx: float, cy: float, r: float, rim: float, spokes: int, spoke_w: int, turn: float = 0.0) -> None:
    """Timber wheel: spokes behind a shaded rim, iron hub (from iron_mine_deep)."""
    for k in range(spokes):
        a = math.radians(turn + 180 * k / spokes)
        dx, dy = math.cos(a) * (r - rim / 2), math.sin(a) * (r - rim / 2)
        ic.beam((cx - dx, cy - dy), (cx + dx, cy + dy), spoke_w, BRACE)
    outer = ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    inner = ic.mask("ellipse", (cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim))
    ring = ImageChops.subtract(outer, inner)
    ic.fill(ring, TIMBER_LIT, (70, 46, 28), radial=(cx - r * 0.6, cy - r * 0.7, r * 2.2), noise=0.25)
    ic.shade(ImageChops.subtract(ring, ic.mask("ellipse", (cx - r + 6, cy - r + 10, cx + r + 6, cy + r + 10))),
             (255, 235, 205), 0.3)
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 28, 20, 200), width=5))
    ic.overlay(lambda d: d.ellipse((cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim),
                                   outline=(40, 28, 20, 200), width=4))
    hub = r * 0.16
    ic.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), "#5a5658", "#222022", edge=4)


def bricks(ic: Icon, mask: Image.Image, box, colors=BRICK, course: float = 16, brick: float = 40) -> None:
    """Brickwork inside ``mask``: per-brick tone, thin dark mortar courses, stagger (from lead_mine_cupola_smelting)."""
    x0, y0, x1, y1 = box
    ic.fill(mask, colors[0], colors[1], (x0, x1), vertical=False, noise=0.2, chroma=0.06)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    for k, y in enumerate(np.arange(y0, y1, course)):
        off = (k % 2) * brick / 2
        for x in np.arange(x0 - brick + off, x1, brick):
            t = rnd(-1, 1)
            q = (x + 2, y + 2, x + brick - 2, y + course - 2)
            d.rectangle(q, fill=(20, 8, 4, int(-t * 60)) if t < 0 else (255, 220, 190, int(t * 36)))
            d.line([(x, y), (x, y + course)], fill=(48, 30, 22, 120), width=3)
        d.line([(x0, y), (x1, y)], fill=(48, 30, 22, 130), width=3)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def smoke(ic: Icon, puffs, light=("#d8d4cc", "#7e7a74")) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath (from lead_mine_cupola_smelting)."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.82 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, light[0], light[1], radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def cake(ic: Icon, cx: float, cy: float, rx: float, h: float = 20) -> None:
    """Finished copper cake: a flat round disc seen from the raised camera, bright dished top, dark rim."""
    ry = rx * 0.36
    side = union(ic.mask("ellipse", (cx - rx, cy - ry + h, cx + rx, cy + ry + h)),
                 ic.mask("rectangle", (cx - rx, cy, cx + rx, cy + h)))
    ic.fill(side, "#a65226", "#4e2010", (cx - rx, cx + rx), vertical=False, noise=0.12)
    ic.overlay(lambda d: d.arc((cx - rx, cy - ry + h, cx + rx, cy + ry + h), 0, 180, fill=(34, 16, 10, 230), width=5))
    for x in (cx - rx, cx + rx):
        ic.line([(x, cy), (x, cy + h)], 5, (34, 16, 10, 230))
    top = ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    ic.fill(top, "#f0a062", "#b4602e", radial=(cx - rx * 0.35, cy - ry * 0.35, rx * 1.5), noise=0.14, chroma=0.05)
    dish = ic.mask("ellipse", (cx - rx * 0.66, cy - ry * 0.62, cx + rx * 0.66, cy + ry * 0.66))
    tint(ic, dish, top, (96, 40, 20), 0.28, 5)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.42, cy - ry * 0.34, cx + rx * 0.2, cy + ry * 0.2)), top, (255, 226, 190), 0.4, 6)
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(44, 22, 12, 230), width=5))


def rock_back(ic: Icon) -> None:
    """Tan rock shoulder behind the works, crusted with malachite."""
    ridge = [(22, 905), (30, 690), (58, 590), (100, 500), (150, 440), (196, 372), (246, 330), (292, 296), (342, 322),
             (392, 300), (440, 340), (492, 392), (540, 470), (590, 560), (640, 660), (680, 905)]
    ic.rock(ridge, ROCK, ROCK_DARK, facets=4)
    fm = ic.poly_mask(ridge)
    with ic.clipped(fm):
        ic.shade(fm, (204, 152, 90), 0.24)
        for y in (470, 600, 730):
            ic.line([(0, y + 50), (300, y + 6), (700, y + 40)], 5, (60, 48, 38, 130))
        crust(ic, [(100, 510), (150, 470), (214, 430)], 58)
        crust(ic, [(46, 640), (122, 616), (214, 604)], 62)
        crust(ic, [(232, 356), (278, 330), (320, 344)], 44, specks=4)
        crust(ic, [(452, 396), (500, 440), (540, 510)], 46, specks=4)
        ic.vein([(160, 700), (190, 760), (178, 800)], 13, CU, CU_DARK, (60, 26, 14))
        ic.shade(ic.mask("rectangle", (0, 760, 1024, 1024)), alpha=0.35, blur=40)
    ic.outline(ridge)


def headframe(ic: Icon) -> None:
    """Braced timber headframe with a sheave wheel on top (from iron_mine_deep, moved left and made wider)."""
    L0, R0, L1, R1, TOP, BASE = 198, 512, 282, 428, 262, 800

    def lx(y: float) -> float:
        return L0 + (L1 - L0) * (BASE - y) / (BASE - TOP)

    def rx(y: float) -> float:
        return R0 + (R1 - R0) * (BASE - y) / (BASE - TOP)

    girts = (664, 528, 396)
    ys = (BASE,) + girts
    for ya, yb in zip(ys[:-1], ys[1:]):
        ic.beam((lx(ya) + 10, ya), (rx(yb) - 10, yb), 16, BRACE)
        ic.beam((rx(ya) - 10, ya), (lx(yb) + 10, yb), 16, BRACE)
    y0 = girts[-1]
    clad = [(lx(y0), y0), (rx(y0), y0), (rx(TOP), TOP), (lx(TOP), TOP)]
    ic.poly(clad, "#8e6644", "#5a3c24", vertical=False, noise=0.3)
    for x in np.arange(lx(y0) + 20, rx(y0), 22):
        xt = lx(TOP) + (x - lx(y0)) * (rx(TOP) - lx(TOP)) / (rx(y0) - lx(y0))
        ic.line([(x, y0), (xt, TOP)], 4, (58, 38, 22, 170))
    ic.rect((336, 306, 376, 354), "#2a201a", "#0c0907", edge=4)  # hatch
    ic.shade(ic.poly_mask([(rx(y0) - 60, y0), (rx(y0), y0), (rx(TOP), TOP), (rx(TOP) - 40, TOP)]), alpha=0.3, blur=12)
    for y in girts:
        ic.beam((lx(y) - 6, y), (rx(y) + 6, y), 24, POST)
    ic.beam((L0, BASE + 10), (L1, TOP), 40, POST)
    ic.beam((R0, BASE + 10), (R1, TOP), 40, POST)
    for x0, x1 in ((L0 - 14, L1 - 14), (R0 - 14, R1 - 14)):
        ic.shade(ic.poly_mask([(x0 - 4, BASE), (x0 + 6, BASE), (x1 + 6, TOP), (x1 - 4, TOP)]), (255, 240, 220), 0.25)
    ic.rect((254, TOP - 24, 456, TOP + 10), "#9a6c44", "#5a3c24")
    ic.shade(ic.mask("rectangle", (254, TOP - 24, 456, TOP - 14)), (255, 240, 215), 0.3)
    ic.beam((310, TOP - 20), (355, 164), 18, BRACE)
    ic.beam((400, TOP - 20), (355, 164), 18, BRACE)
    wheel(ic, 355, 164, 96, 18, 4, 12, turn=20)
    # hoisting rope down the shaft, with a laden kibble; back-stay towards the furnace side
    ic.line([(262, 172), (262, 610)], 9, DARK)
    ic.line([(262, 172), (262, 610)], 4, (170, 140, 96))
    ore_lumps(ic, [(238, 620), (264, 610), (288, 622)], 24, 0.4)
    ic.poly([(226, 624), (300, 624), (292, 676), (234, 676)], "#8a6a4a", "#3e2a1a")
    ic.line([(228, 640), (298, 640)], 7, IRON)
    ic.line([(233, 666), (293, 666)], 7, IRON)
    ic.beam((452, 262), (604, 720), 22, BRACE)


def furnace(ic: Icon) -> None:
    """Tall tapering brick chimney and a low brick reverberatory vault with buckstays and a glowing door."""
    BASE = 892
    CX0, CX1, CTOP = 780, 900, 150
    chim = [(CX0, BASE), (CX0 + 22, CTOP + 40), (CX1 - 22, CTOP + 40), (CX1, BASE)]
    cm = ic.poly_mask(chim)
    bricks(ic, cm, (CX0, CTOP, CX1, BASE), course=16, brick=34)
    tint(ic, ic.mask("rectangle", (CX0 + 66, CTOP, CX1 + 10, BASE)), cm, (0, 0, 0), 0.35, 12)
    tint(ic, ic.mask("rectangle", (CX0, CTOP, CX1, CTOP + 120)), cm, (20, 14, 12), 0.5, 20)  # soot
    ic.outline(chim, 5)
    cap = [(CX0 + 8, CTOP + 44), (CX0 + 12, CTOP + 12), (CX1 - 12, CTOP + 12), (CX1 - 8, CTOP + 44)]
    bricks(ic, ic.poly_mask(cap), (CX0, CTOP, CX1, CTOP + 44), course=16, brick=30)
    tint(ic, ic.poly_mask(cap), None, (20, 14, 12), 0.35)
    ic.outline(cap, 5)
    for y in (CTOP + 220, CTOP + 400):
        f = (y - CTOP - 40) / (BASE - CTOP - 40)
        ic.line([(CX0 + 22 - 22 * f - 3, y), (CX1 - 22 + 22 * f + 3, y)], 8, (38, 36, 38))

    FX0, FX1, FTOP = 532, 812, 640
    body = union(ic.mask("rectangle", (FX0, FTOP + 70, FX1, BASE)),
                 ic.mask("chord", (FX0, FTOP, FX1, FTOP + 170), start=180, end=360))
    bricks(ic, body, (FX0, FTOP, FX1, BASE), course=18, brick=38)
    tint(ic, ic.mask("rectangle", (FX0 + 170, FTOP, FX1, BASE)), body, (0, 0, 0), 0.3, 20)
    tint(ic, ic.mask("rectangle", (FX0, FTOP, FX1, FTOP + 50)), body, (20, 14, 10), 0.35, 14)
    tint(ic, ic.mask("chord", (FX0 + 10, FTOP + 4, FX1 - 10, FTOP + 130), start=200, end=300), body,
         (255, 230, 200), 0.3, 6)
    ic.overlay(lambda d: d.arc((FX0, FTOP, FX1, FTOP + 170), 180, 360, fill=(40, 26, 18, 210), width=6))
    ic.line([(FX0, FTOP + 85), (FX0, BASE), (FX1, BASE), (FX1, FTOP + 85)], 6)
    DX0, DX1 = 586, 690
    door = union(ic.mask("ellipse", (DX0, 744, DX1, 840)), ic.mask("rectangle", (DX0, 792, DX1, 868)))
    ic.fill(door, "#ffcc6a", "#b43c14", radial=((DX0 + DX1) / 2, 846, 84), noise=0.1)
    ic.line([(DX0 - 8, 870), (DX1 + 8, 870)], 12, (40, 38, 40))
    tint(ic, ic.mask("ellipse", (DX0 - 80, 700, DX1 + 80, 930)), body, (255, 130, 50), 0.35, 24)
    ic.overlay(lambda d: d.arc((DX0 - 10, 734, DX1 + 10, 850), 180, 360, fill=(40, 26, 18, 210), width=6))
    for x in (FX0 + 14, 572, 706, 796):
        top = FTOP + 85 - 80 * math.sqrt(max(0.0, 1 - ((x - (FX0 + FX1) / 2) / ((FX1 - FX0) / 2)) ** 2))
        ic.line([(x, top + 6), (x, BASE + 6)], 14, (34, 34, 38))
        ic.line([(x - 3, top + 8), (x - 3, BASE)], 3, (120, 120, 126))
        ic.draw.ellipse((x - 9, top - 2, x + 9, top + 14), fill=(44, 44, 48, 255))
    ic.line([(FX0 - 10, 716), (FX1 + 10, 716)], 10, (34, 34, 38))


def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.97
    smoke(ic, [(1000, 92, 30), (960, 84, 40), (908, 92, 46), (868, 116, 40)])
    rock_back(ic)

    # ---- ground apron in spoil, green and copper-red specks
    apron = [(15, 972), (50, 894), (300, 884), (760, 884), (970, 898), (1012, 972)]
    ic.poly(apron, "#8e7656", "#56452f", noise=0.3)
    with ic.clipped(ic.poly_mask(apron)):
        for _ in range(24):
            x, y = ic.random.uniform(60, 960), ic.random.uniform(900, 962)
            col = (80, 160, 120) if ic.random.random() < 0.55 else (196, 104, 58)
            ic.shade(ic.mask("ellipse", (x - 9, y - 6, x + 9, y + 6)), col, 0.7)

    # ---- stone shaft collar and the headframe over it
    ic.poly([(172, 812), (536, 812), (514, 770), (194, 770)], "#a39684", "#6e6458", noise=0.25)
    ic.poly([(214, 804), (494, 804), (480, 780), (228, 780)], "#1c140e", "#060403", edge=0, noise=0.05)
    furnace(ic)
    headframe(ic)
    ic.stonewall((176, 812, 532, 895), "#a39684", "#766b5e", course=40)
    ic.shade(ic.mask("rectangle", (176, 812, 532, 836)), alpha=0.3, blur=6)

    # ---- broad ore mound bottom left, laden tub in the middle, copper cakes bottom right
    mound(ic, 16, 262, 968, 760, 36, 5, cu_share=0.34, power=0.55)
    tub(ic, 306, 540, 866, 940)
    ic.shade(ic.mask("ellipse", (620, 930, 1010, 1006)), alpha=0.4, blur=10)
    for x, y, r in ((700, 952, 72), (844, 958, 76), (946, 940, 56)):
        cake(ic, x, y, r)
    for x, y, r in ((770, 918, 70), (900, 912, 60)):
        cake(ic, x, y, r)
    cake(ic, 826, 876, 62)
