"""Gem Gravel Pit (gem_gravel_pit): a shallow gravel digging with a hanging sieve, baskets and a pan.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/gem_gravel_pit/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/gem_gravel_pit

Identity: hand work in alluvial gravel. A low spoil bank of rounded pebbles sloping off to the left
(wet at the foot, dry on the crest) with a shovel in it, the pit in front of it cut down to silty water, a pole tripod with a round sieve hanging over a
wash tub (water dripping through), baskets of dug gravel and a wooden pan with a few bright stones.
Vanilla pits are a treadwheel crane over a heap; this reads through the tripod sieve, the pebbles
and the coloured stones. Local helpers: ``layer``/``composite``, ``tint``, ``timber``, ``pebbles``
(gravel texture), ``gem`` (cut-looking stone with a glint), ``sieve`` (hanging riddle), ``wicker``
(basket of gravel), ``pan``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 53
REFS = ("sand_pit", "clay_pit", "jewelry_guild", "stone_quarry")

GRAVEL, GRAVEL_DK = "#9c8a70", "#554632"
PEBBLES = [(168, 156, 138), (140, 132, 120), (182, 162, 124), (120, 110, 98), (160, 120, 88), (196, 186, 166),
           (110, 116, 118), (150, 140, 110)]
EARTH, EARTH_DK = "#8a6a4a", "#4e3a28"
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


def sieve(ic: Icon, cx: float, cy: float, r: float, depth: float) -> None:
    """Hanging round riddle seen from above: wooden band, woven mesh holding gravel, drips below."""
    ry = r * 0.36
    side = [(cx + math.cos(a) * r, cy + math.sin(a) * ry) for a in np.linspace(0, math.pi, 24)]
    side += [(cx + math.cos(a) * r * 0.97, cy + depth + math.sin(a) * ry) for a in np.linspace(math.pi, 0, 24)]
    sm = ic.poly_mask(side)
    ic.fill(sm, "#a27850", "#5a3c22", (cx - r, cx + r), vertical=False, noise=0.2)
    tint(ic, ic.mask("rectangle", (cx + r * 0.3, cy - 10, cx + r + 10, cy + depth + ry + 10)), sm, (10, 6, 2), 0.35, 12)
    ic.outline(side, 4, (40, 26, 16, 190))
    rim = ic.mask("ellipse", (cx - r, cy - ry, cx + r, cy + ry))
    ic.fill(rim, "#b48a5e", "#6e4c2e", (cy - ry, cy + ry), noise=0.2)
    inner = ic.mask("ellipse", (cx - r * 0.88, cy - ry * 0.8, cx + r * 0.88, cy + ry * 0.86))
    ic.fill(inner, "#6a5a48", "#3e3428", (cy - ry, cy + ry), noise=0.2)
    pebbles(ic, inner, (cx - r, cy - ry, cx + r, cy + ry), r=(6, 11), density=1.3, scale_y=(0.9, 1.0))
    lay, d = layer()
    for x in np.arange(cx - r, cx + r, 18):  # mesh showing between the stones
        d.line([(x, cy - ry), (x + 12, cy + ry)], fill=(40, 30, 20, 90), width=2)
    composite(ic, lay, inner)
    tint(ic, ic.mask("ellipse", (cx - r * 0.9, cy - ry * 0.85, cx + r * 0.9, cy - ry * 0.2)), inner, (0, 0, 0), 0.35, 6)
    ic.overlay(lambda d: d.ellipse((cx - r, cy - ry, cx + r, cy + ry), outline=(40, 26, 16, 200), width=4))


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


def pan(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> None:
    """Shallow wooden washing pan (batea) with wet sand and a few bright stones."""
    ic.fill(ic.mask("ellipse", (cx - rx, cy - ry + 10, cx + rx, cy + ry + 16)), "#5a3c22", "#3a2614", noise=0.1)
    outer = ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))
    ic.fill(outer, "#a47a50", "#5e4026", radial=(cx - rx * 0.3, cy - ry, rx * 1.4), noise=0.2)
    inner = ic.mask("ellipse", (cx - rx * 0.78, cy - ry * 0.7, cx + rx * 0.78, cy + ry * 0.74))
    ic.fill(inner, "#6c6a60", "#3c3c38", radial=(cx, cy, rx * 0.8), noise=0.2)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.7, cy - ry * 0.3, cx + rx * 0.4, cy + ry * 0.6)), inner, (130, 170, 176), 0.5, 6)
    for i, (dx, dy, r) in enumerate(((-0.4, 0.05, 27), (0.02, 0.28, 25), (0.36, -0.08, 29), (-0.08, -0.3, 22), (0.5, 0.32, 20))):
        gem(ic, cx + dx * rx, cy + dy * ry, r, GEMS[i % len(GEMS)])
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(40, 26, 16, 200), width=4))


def cobble(ic: Icon, cx: float, cy: float, r: float, color) -> None:
    """A larger rounded river stone lying in the gravel: lit cap, dark underside, contact shadow."""
    ic.shade(ic.mask("ellipse", (cx - r * 1.1, cy - r * 0.2, cx + r * 1.2, cy + r * 0.85)), (20, 14, 8), 0.4, blur=4)
    pts = ic.jitter(cx, cy, r, r * 0.7, 10, 0.08)
    m = ic.poly_mask(pts)
    ic.fill(m, color, tuple(int(v * 0.5) for v in color), radial=(cx - r * 0.4, cy - r * 0.5, r * 1.8), noise=0.12)
    tint(ic, ic.mask("ellipse", (cx - r * 0.7, cy - r * 0.6, cx + r * 0.1, cy - r * 0.1)), m, (255, 250, 238), 0.3, 3)
    ic.outline(pts, 3, (40, 30, 20, 150))


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9
    ic.grade["gamma"] = 0.68
    R = ic.random

    # ---- spoil bank of dug gravel, back left: crest on the right, a long slope down to the left
    top = [(20, 820), (40, 772), (90, 724), (150, 680), (220, 640), (290, 596), (350, 556), (400, 526), (440, 510),
           (478, 506), (516, 524), (556, 572), (590, 650), (616, 740)]
    bank = top + [(630, 836), (20, 842)]
    bm = ic.poly_mask(bank)
    ic.fill(bm, GRAVEL, GRAVEL_DK, radial=(430, 500, 560), noise=0.3, chroma=0.12)
    pebbles(ic, bm, (20, 496, 632, 846), r=(9, 18), density=1.0, scale_y=(0.7, 1.05))
    # dry, pale crest along the top edge
    crest = top + [(x + 10, y + 70) for x, y in top[::-1]]
    tint(ic, ic.poly_mask(crest), bm, (250, 236, 206), 0.2, 16)
    # sandy streaks running down the slope to the left
    for sx, sy, ln in ((330, 574, 190), (420, 530, 240), (230, 634, 130)):
        dx, dy = -0.62 * ln, 0.78 * ln
        streak = [(sx - 10, sy), (sx + 12, sy + 4), (sx + dx + 26, sy + dy), (sx + dx - 6, sy + dy + 4)]
        tint(ic, ic.poly_mask(streak), bm, (214, 186, 136), 0.45, 6)
    # right flank turned away from the light
    tint(ic, ic.poly_mask([(470, 500), (640, 620), (640, 846), (430, 846)]), bm, (10, 6, 2), 0.42, 40)
    # darker, wet gravel in a band along the pit edge
    tint(ic, ic.mask("rectangle", (0, 740, SIZE, 860)), bm, (30, 26, 22), 0.62, 16)
    tint(ic, ic.mask("rectangle", (0, 790, SIZE, 860)), bm, (60, 76, 80), 0.18, 10)
    for _ in range(26):  # damp patches and dry flecks break up the texture
        x, y, r = R.uniform(80, 580), R.uniform(560, 800), R.uniform(16, 34)
        tint(ic, ic.poly_mask(ic.jitter(x, y, r, r * 0.6, 9, 0.3)), bm, R.choice([(40, 30, 20), (255, 240, 214)]),
             R.uniform(0.1, 0.2), 6)
    for cx, cy, r, c in ((150, 740, 26, (150, 140, 128)), (300, 690, 30, (176, 160, 130)), (470, 610, 24, (120, 124, 126)),
                         (540, 720, 28, (160, 124, 92)), (90, 792, 22, (140, 132, 120)), (380, 780, 32, (130, 122, 110))):
        cobble(ic, cx, cy, r, c)
    ic.outline(bank, 5, (40, 30, 22, 200))
    # a couple of stones showing in the gravel
    for x, y, r, c in ((210, 720, 15, GEMS[0]), (520, 660, 14, GEMS[1]), (340, 640, 12, GEMS[2])):
        gem(ic, x, y, r, c)
    # shovel stuck in the crest, its long haft leaning up to the left
    timber(ic, (470, 560), (330, 318), 16, "#9a7450", "#5e4128")
    ic.line([(316, 326), (344, 310)], 14, (60, 40, 24))
    ic.poly([(446, 540), (500, 518), (524, 600), (484, 620)], "#8a8a90", "#48484e", edge=4)

    # ---- pole tripod with the sieve over a wash tub, right
    AX, AY = 770, 290
    timber(ic, (AX, AY), (850, 820), 26, "#8a6a48", "#4e3824")  # back leg
    # wash tub under the sieve, water with drips
    tx0, tx1, ttop, tbase = 650, 900, 760, 870
    lip = 30
    tub = [(tx0, ttop), (tx1, ttop), (tx1 - 16, tbase)] + \
          [((tx0 + tx1) / 2 + math.cos(a) * ((tx1 - tx0) / 2 - 16), tbase + math.sin(a) * lip * 0.8)
           for a in np.linspace(0, math.pi, 14)] + [(tx0 + 16, tbase)]
    tm = ic.poly_mask(tub)
    ic.fill(tm, "#a4764c", "#4c3120", radial=(tx0 + 70, ttop, 300), noise=0.16)
    tint(ic, ic.mask("rectangle", (tx0 + 160, ttop, tx1 + 10, tbase + lip)), tm, (16, 8, 4), 0.35, 12)
    for f in (0.3, 0.78):
        y = ttop + (tbase - ttop) * f
        ic.line([((tx0 + tx1) / 2 + math.cos(a) * ((tx1 - tx0) / 2 - 16 * f), y + math.sin(a) * lip * 0.8)
                 for a in np.linspace(0, math.pi, 14)], 9, (58, 54, 52))
    ic.outline(tub, 4, (40, 26, 16, 190))
    ic.fill(ic.mask("ellipse", (tx0, ttop - lip, tx1, ttop + lip)), "#6a4a2e", "#3e2a18", (ttop - lip, ttop + lip))
    ic.fill(ic.mask("ellipse", (tx0 + 12, ttop - lip + 8, tx1 - 12, ttop + lip - 6)), WATER, WATER_DK,
            (ttop - lip, ttop + lip), noise=0.08)
    ic.overlay(lambda d: [d.line([(cx - 22, ttop + dy), (cx + 22, ttop + dy)], fill=(230, 242, 244, 170), width=4)
                          for cx, dy in ((720, -6), (800, 4), (850, -10))])
    SX, SY, SR = 772, 580, 150
    lay, d = layer()
    for x in (712, 740, 774, 804, 832):  # drips falling through the mesh
        y0 = SY + 60 + R.uniform(0, 14)
        d.line([(x, y0), (x + R.uniform(-3, 3), ttop - 6)], fill=(200, 226, 232, 170), width=4)
    ic.image.alpha_composite(lay)
    # ropes and sieve
    for dx in (-0.8, 0.0, 0.8):
        ic.line([(AX, AY + 20), (SX + SR * dx, SY + (0 if dx else -SR * 0.3))], 5, (70, 56, 40))
    sieve(ic, SX, SY, SR, 36)
    timber(ic, (AX, AY), (600, 850), 28)  # front legs
    timber(ic, (AX, AY), (990, 860), 28)
    ic.fill(ic.mask("ellipse", (AX - 26, AY - 22, AX + 26, AY + 22)), "#7a5a3a", "#4a3220", noise=0.2)  # lashing
    ic.overlay(lambda d: [d.line([(AX - 24, AY - 12 + k * 10), (AX + 24, AY - 4 + k * 10)], fill=(60, 44, 28, 220), width=4)
                          for k in range(3)])

    # ---- the pit in front of the bank: trodden rim, dark cut earth wall, brown-grey water
    rim = ic.jitter(300, 872, 292, 88, 18, 0.06)
    rm = ic.poly_mask(rim)
    ic.fill(rm, EARTH, EARTH_DK, (790, 960), noise=0.34)
    pebbles(ic, rm, (0, 780, 600, 960), r=(6, 11), density=0.5, scale_y=(1, 1))
    ic.outline(rim, 4, (40, 28, 18, 150))
    cut = ic.jitter(300, 874, 226, 64, 28, 0.035)
    cm = ic.poly_mask(cut)
    ic.fill(cm, "#4e3826", "#241810", (812, 900), noise=0.3)  # cut earth wall
    lay, d = layer()
    for k in range(3):  # faint strata in the cut wall
        y = 834 + k * 10
        for x0 in range(80, 540, 90):
            d.line([(x0 + R.uniform(0, 30), y + R.uniform(-3, 3)), (x0 + R.uniform(50, 90), y + R.uniform(-3, 3))],
                   fill=(150, 116, 80, 50), width=3)
    composite(ic, lay, cm)
    pool = ic.intersect(ic.mask("ellipse", (60, 860, 540, 960)), cm)
    ic.fill(pool, "#5a4e3c", "#241e16", (862, 936), noise=0.1, chroma=0.05)  # silty water
    tint(ic, ic.mask("rectangle", (0, 858, SIZE, 876)), pool, (30, 26, 20), 0.5, 5)  # shadow of the far wall
    tint(ic, ic.mask("ellipse", (110, 874, 290, 902)), pool, (226, 232, 226), 0.3, 8)  # sky sheen
    ic.overlay(lambda d: [d.line([(x0, y), (x0 + L, y + 1)], fill=(236, 242, 238, 190), width=4)
                          for x0, y, L in ((130, 884, 70), (220, 902, 54), (330, 878, 44))], pool)
    ic.outline(cut, 4, (30, 22, 14, 170))

    # ---- basket of dug gravel and the washing pan with stones, front
    wicker(ic, 800, 1000, 842, 960)
    pan(ic, 490, 922, 184, 60)
