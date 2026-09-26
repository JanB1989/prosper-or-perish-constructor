"""Quicksilver Retort (quicksilver_retort): a brick retort furnace roasting cinnabar into mercury.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/quicksilver_retort/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/quicksilver_retort

Identity: a long brick furnace under a tiled hood with a tall chimney; three clay retorts glow in
arched ports in its face, their necks running down into stoneware receivers at its foot. A clay
pipe from the furnace end feeds a big glass condensing flask on a bench on the right, a pool of
bright quicksilver in its belly. A heap of red cinnabar at the left ties it to the pit. Tier 1 of
the mercury chain: masonry, fire and glass where the pit had rock and a windlass.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 43
REFS = ("tatara", "schwaz_mine", "apothecary", "local_smelters")

WOOD, WOOD_DK = "#8a6240", "#4e3522"
BRICK, BRICK_DK = "#a66a50", "#5a3428"
CLAY, CLAY_DK = "#b88a5c", "#5e3e26"
RED, RED_DK = "#d23a2a", "#5a1210"

FX0, FX1 = 110, 690        # furnace
FTOP, FBOT = 420, 800
PORTS = (220, 400, 580)    # retort port centres


# ---- helpers (copied from canal_lock_works / cinnabar_pit, candidates for the kit) -------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
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
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def bricks(ic: Icon, pts, base=BRICK, dark=BRICK_DK, course: float = 30, length=(58, 84), span=None) -> Image.Image:
    """Brick face: per-brick tone, soft lit top edge, pale mortar, soot from above; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, base, dark, span or (min(ys), max(ys) + 120), noise=0.22, chroma=0.14)
    R = ic.random
    lay, d = layer()
    y, k = min(ys), 0
    while y < max(ys):
        x = min(xs) - (R.randint(10, 40) if k % 2 else 0)
        while x < max(xs):
            w = R.randint(*length)
            t = R.uniform(-1, 1)
            d.rectangle((x, y, x + w, y + course), fill=(255, 220, 190, int(30 * t)) if t > 0 else (30, 14, 8, int(-50 * t)))
            d.line([(x + 3, y + 3), (x + w - 4, y + 3)], fill=(255, 236, 214, 50), width=3)
            d.line([(x, y), (x, y + course)], fill=(196, 176, 150, 150), width=4)
            x += w
        d.line([(min(xs), y), (max(xs), y)], fill=(196, 176, 150, 150), width=4)
        y += course
        k += 1
    composite(ic, lay, m)
    return m


def smoke(ic: Icon, x: float, y: float, h: float) -> None:
    """Drifting plume of puffs, lit upper left, thinning upwards."""
    R = ic.random
    for i in range(7):
        t = i / 6
        cx = x + 90 * t ** 1.3 + R.uniform(-8, 8)
        cy = y - h * t
        r = 30 + 26 * t
        box = (cx - r, cy - r * 0.8, cx + r, cy + r * 0.8)
        g = int(150 + 50 * t)
        ic.fill(ic.mask("ellipse", box), (g + 30, g + 28, g + 24), (g - 50, g - 52, g - 54),
                radial=(cx - r * 0.5, cy - r * 0.6, r * 1.8), noise=0.2)


def glow(ic: Icon, mask: Image.Image, cx: float, cy: float, r: float) -> None:
    ic.fill(mask, "#ffe08a", "#8a2410", radial=(cx, cy, r), noise=0.18)


# ---- parts -------------------------------------------------------------------------------------
def chimney(ic: Icon) -> None:
    cx0, cx1, top = 250, 344, 150
    bricks(ic, [(cx0, top), (cx1, top), (cx1 + 6, FTOP), (cx0 - 6, FTOP)], "#9a6048", "#4e2c22", course=26,
           length=(40, 56))
    ic.shade(ic.mask("rectangle", (cx0 + 50, top, cx1 + 10, FTOP)), alpha=0.3, blur=10)
    ic.rect((cx0 - 14, top - 26, cx1 + 14, top + 4), "#8a5a44", "#4e2e22", edge=5)
    ic.shade(ic.mask("rectangle", (cx0 - 10, top, cx1 + 10, top + 60)), (20, 16, 14), 0.4, blur=14)  # soot
    smoke(ic, (cx0 + cx1) / 2, top - 36, 84)


def hood(ic: Icon) -> None:
    """Tiled hood over the furnace top, carried on the end walls."""
    pts = [(FX0 - 40, FTOP + 10), (FX1 + 40, FTOP + 10), (FX1 - 10, 318), (FX0 + 10, 318)]
    ic.tiles(pts, "#a8624a", "#6a3a2c", course=26, stagger=36)
    R = ic.random
    rm = ic.poly_mask(pts)
    for _ in range(60):
        x, y = R.uniform(FX0 - 30, FX1 + 30), 318 + R.randrange(0, 4) * 26
        ic.shade(ic.intersect(rm, ic.mask("rectangle", (x, y + 3, x + R.uniform(18, 34), y + 24))),
                 (28, 16, 10) if R.random() < 0.6 else (255, 226, 190), R.uniform(0.1, 0.28))
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (FX0 + 120, 300, FX0 + 260, 360))), (20, 16, 14), 0.3, blur=16)
    ic.line([(FX0 - 40, FTOP + 10), (FX1 + 40, FTOP + 10)], 10, (70, 40, 30))
    ic.shade(ic.poly_mask([(FX0 + 10, 318), (FX1 - 10, 318), (FX1 - 12, 340), (FX0 + 12, 340)]), (255, 236, 200), 0.18)


def furnace(ic: Icon) -> None:
    face = [(FX0, FTOP), (FX1, FTOP), (FX1, FBOT), (FX0, FBOT)]
    fm = bricks(ic, face)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, FTOP, SIZE, FTOP + 50))), alpha=0.5, blur=14)  # under the hood
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, FBOT - 90, SIZE, FBOT))), (20, 16, 14), 0.3, blur=20)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (FX1 - 70, 0, SIZE, SIZE))), alpha=0.25, blur=20)
    for _ in range(8):  # soot and lime streaks
        x = ic.random.uniform(FX0, FX1)
        ic.shade(ic.intersect(fm, ic.mask("rectangle", (x, FTOP, x + ic.random.uniform(10, 26),
                                                        FTOP + ic.random.uniform(60, 200)))),
                 (24, 18, 16) if ic.random.random() < 0.7 else (230, 220, 200), ic.random.uniform(0.1, 0.2), blur=6)
    # plinth of dressed stone
    ic.rect((FX0 - 14, FBOT - 40, FX1 + 14, FBOT + 10), "#a89886", "#6a5e52", edge=5)
    ic.line([(FX0 - 12, FBOT - 38), (FX1 + 12, FBOT - 38)], 4, (255, 244, 226, 90))
    for cx in PORTS:
        port(ic, cx)
    ic.outline(face)


def port(ic: Icon, cx: float) -> None:
    """Arched port with a clay retort bedded in the fire; soot above, glow spilling on the bricks."""
    w, y0, y1 = 118, 470, 628
    arch = ic.mask("ellipse", (cx - w / 2, y0, cx + w / 2, y0 + w))
    arch = ImageChops.lighter(arch, ic.mask("rectangle", (cx - w / 2, y0 + w / 2, cx + w / 2, y1)))
    # voussoirs
    ring = ImageChops.subtract(arch.filter(ImageFilter.MaxFilter(29)), arch)
    ic.fill(ring, "#b27658", "#6a3a2c", (y0 - 14, y1), noise=0.2)
    ic.overlay(lambda d: [d.line([(cx + math.cos(a) * w * 0.5, y0 + w / 2 + math.sin(a) * w * 0.5),
                                  (cx + math.cos(a) * (w * 0.5 + 14), y0 + w / 2 + math.sin(a) * (w * 0.5 + 14))],
                                 fill=(60, 34, 24, 180), width=4) for a in np.linspace(math.pi, 2 * math.pi, 7)])
    ic.shade(ic.mask("ellipse", (cx - 70, y0 - 110, cx + 70, y0 + 30)), (20, 14, 12), 0.35, blur=18)  # soot
    glow(ic, arch, cx, y1 - 20, 150)
    # retort body silhouetted in the fire, rim lit by it
    body = ic.mask("ellipse", (cx - 42, y1 - 96, cx + 42, y1 - 16))
    ic.fill(body, "#b27a4a", "#4a2616", radial=(cx - 16, y1 - 20, 100), noise=0.2)
    ic.shade(ImageChops.subtract(body, body.filter(ImageFilter.MinFilter(9))), (255, 170, 60), 0.7)
    ic.shade(ic.mask("ellipse", (cx - 26, y1 - 86, cx - 4, y1 - 66)), (255, 236, 200), 0.35, blur=3)
    ic.overlay(lambda d: d.ellipse((cx - 42, y1 - 96, cx + 42, y1 - 16), outline=(40, 22, 12, 200), width=4))
    ic.fill(ic.mask("rectangle", (cx - w / 2, y1 - 14, cx + w / 2, y1)), "#ffd070", "#c05018", (y1 - 14, y1), noise=0.3)
    # glow spilling onto the bricks below the port
    ic.shade(ic.mask("ellipse", (cx - 90, y1 - 30, cx + 90, y1 + 70)), (255, 150, 60), 0.35, blur=24)
    # neck from the retort down to its receiver
    neck(ic, [(cx + 16, y1 - 40), (cx + 40, y1 + 10), (cx + 58, y1 + 70)], 22, 12)
    receiver(ic, cx + 58, y1 + 70)


def neck(ic: Icon, path, w0: float, w1: float) -> None:
    pts = np.array(path, float)
    n = len(pts)
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        a = a / np.hypot(*a)
        nrm = np.array([-a[1], a[0]])
        w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        left.append(tuple(p + nrm * w))
        right.append(tuple(p - nrm * w))
    poly = left + right[::-1]
    ic.poly(poly, CLAY, CLAY_DK, (min(pts[:, 0]) - 20, max(pts[:, 0]) + 20), vertical=False, edge=4)
    ic.line([tuple(p + np.array([-3, -2])) for p in pts[:-1]], 4, (255, 236, 200, 110))


def receiver(ic: Icon, cx: float, top: float) -> None:
    """Stoneware receiver jar at the furnace foot."""
    h, w = 96, 74
    body = [(cx - w * 0.3, top), (cx + w * 0.3, top), (cx + w * 0.5, top + h * 0.35), (cx + w * 0.45, top + h),
            (cx - w * 0.45, top + h), (cx - w * 0.5, top + h * 0.35)]
    ic.poly(body, "#9a8c78", "#4e463c", (cx - w / 2, cx + w / 2), vertical=False, edge=4)
    ic.shade(ic.poly_mask([(cx - w * 0.36, top + h * 0.2), (cx - w * 0.2, top + h * 0.2), (cx - w * 0.22, top + h * 0.8),
                           (cx - w * 0.36, top + h * 0.8)]), (255, 248, 230), 0.25, blur=4)
    ic.ellipse((cx - w * 0.3, top - 8, cx + w * 0.3, top + 10), "#6e6254", "#3a342c", edge=4)


def condenser(ic: Icon) -> None:
    """Glass condensing flask on a bench, quicksilver pooled in its belly, fed by a clay pipe."""
    # bench
    ic.rect((720, 700, 1000, 740), "#9a7048", "#5a3e26", edge=5)
    for x in (744, 976):
        timber(ic, (x, 738), (x, 830), 22)
    ic.shade(ic.mask("rectangle", (720, 740, 1000, 770)), alpha=0.4, blur=8, clip=True)
    cx, cy, r = 862, 590, 112
    # straw ring the flask sits in
    ic.ellipse((cx - 80, 680, cx + 80, 716), "#c8a86a", "#7a6036", edge=4)
    # neck and body
    nm = ic.mask("rectangle", (cx - 26, 400, cx + 26, cy - r + 20))
    ic.fill(nm, "#c4d2cc", "#6e8680", (cx - 26, cx + 26), vertical=False, noise=0.08)
    ic.outline([(cx - 26, 400), (cx + 26, 400), (cx + 26, cy - r + 20), (cx - 26, cy - r + 20)], 5)
    bm = ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    ic.fill(bm, "#cadad4", "#56706c", radial=(cx - r * 0.4, cy - r * 0.5, r * 2.0), noise=0.08, chroma=0.05)
    # pooled mercury: a bright silver lens in the lower belly
    pool = ic.intersect(bm, ic.mask("ellipse", (cx - r * 1.2, cy + r * 0.25, cx + r * 1.2, cy + r * 1.9)))
    ic.fill(pool, "#f2f4f4", "#5e666c", (cy + r * 0.25, cy + r), noise=0.06, chroma=0.02)
    ic.overlay(lambda d: d.arc((cx - r * 0.95, cy + r * 0.22, cx + r * 0.95, cy + r * 0.52), 180, 360,
                               fill=(255, 255, 255, 230), width=7), bm)
    ic.shade(ic.intersect(pool, ic.mask("rectangle", (cx + r * 0.2, 0, SIZE, SIZE))), (20, 28, 34), 0.35, blur=10)
    # glass: highlight and reflections
    ic.overlay(lambda d: d.arc((cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78), 190, 250,
                               fill=(255, 255, 255, 210), width=12))
    ic.overlay(lambda d: d.ellipse((cx + r * 0.3, cy - r * 0.5, cx + r * 0.46, cy - r * 0.3), fill=(255, 255, 255, 170)))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 50, 50, 210), width=6))
    ic.line([(cx - 18, 410), (cx - 18, cy - r + 14)], 5, (255, 255, 255, 150))
    # clay pipe from the furnace end into the flask neck
    neck(ic, [(FX1 - 10, 470), (760, 440), (cx - 10, 408)], 34, 26)
    ic.ellipse((cx - 32, 390, cx + 32, 412), "#9a8c78", "#4e463c", edge=4)  # luting


def draw(ic: Icon) -> None:
    chimney(ic)
    hood(ic)
    furnace(ic)
    condenser(ic)
    # cinnabar heap bottom left and a few spilt lumps
    ic.heap(20, 250, 850, 660, 30, 5, body=("#8a2a20", "#3a100c"), lump=(RED, RED_DK),
            odd=("#a89888", "#4a3e36"), odd_share=0.18)
    # firewood by the bench
    for i, (x, y) in enumerate(((650, 812), (700, 806), (676, 780))):
        ic.ellipse((x - 26, y - 26, x + 26, y + 26), "#b08a5a", "#6a4a2c", edge=5)
        ic.overlay(lambda d, x=x, y=y: d.ellipse((x - 12, y - 12, x + 12, y + 12), outline=(90, 60, 34, 200), width=3))
