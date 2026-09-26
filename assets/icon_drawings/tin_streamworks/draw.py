"""Tin Streamworks (tin_streamworks): streaming alluvial gravel for black cassiterite.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/tin_streamworks/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tin_streamworks

Identity: a heavy plank launder on two A-frame trestles carries bright water off a small turfed
gravel bank and drops it as a sheet into a long plank streaming box (tye) standing in a blue
stream; the washed gravel in the box shows black tin grains caught behind cross-riffles, a shovel
leans on the box and a heap of glinting cassiterite stands on a gravel spit on the right. Tier 0 of
the tin chain (the stamping mill adds the wheel, the roof and the stamps).
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 31
REFS = ("sand_pit", "clay_pit", "sawmill", "irrigation_systems")

WOOD, WOOD_DK = "#8a6240", "#4e3522"
W_LIGHT, W_DEEP = "#3c98e0", "#0c4892"    # stream: vanilla watermill blue after the grade
W_RUN, W_RUN_DK = "#bfe6ff", "#4c9ad8"    # water running in the launder
GRAVEL, GRAVEL_DK = "#ae9470", "#5e4c38"
TIN, TIN_DK = "#806654", "#241a14"  # cassiterite: brown-black, greasy lustre


# ---- helpers (copied from canal_lock_works, candidates for the kit) ------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, vertical_boards: bool = True) -> Image.Image:
    """Board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    lo, hi = (min(xs), max(xs)) if vertical_boards else (min(ys), max(ys))
    v = lo
    while v < hi:
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        col = (255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t))
        if vertical_boards:
            d.rectangle((v, min(ys), v + w, max(ys)), fill=col)
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        else:
            d.rectangle((min(xs), v, max(xs), v + w), fill=col)
            gy = v + R.uniform(4, w - 4)
            d.line([(min(xs), gy), (max(xs), gy + R.uniform(-3, 3))], fill=(40, 24, 12, 60), width=2)
            d.line([(min(xs), v), (max(xs), v)], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


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


def pebbles(ic: Icon, mask: Image.Image, n: int, size=(4, 12),
            tones=((198, 180, 150), (150, 128, 100), (120, 104, 88), (92, 80, 70), (170, 150, 128)),
            hi: int = 80) -> None:
    """Gravel texture: small stones with a lit top and a dark underside, clipped to ``mask``."""
    R = ic.random
    box = mask.getbbox()
    lay, d = layer()
    for _ in range(n):
        x, y = R.uniform(box[0], box[2]), R.uniform(box[1], box[3])
        r = R.uniform(*size)
        c = R.choice(tones)
        pts = ic.jitter(x, y, r, r * 0.7, 7, 0.22)
        d.polygon([(px, py + 3) for px, py in pts], fill=(30, 24, 18, 110))
        d.polygon(pts, fill=c + (R.randint(150, 220),))
        d.ellipse((x - r * 0.6, y - r * 0.6, x + r * 0.1, y - r * 0.1), fill=(255, 248, 230, hi))
    composite(ic, lay, mask)


def tufts(ic: Icon, x: float, y: float, w: float) -> None:
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 36)
        tip = (bx + R.uniform(-12, 12), y - h)
        col = (R.randint(92, 128), R.randint(108, 136), R.randint(48, 66), 235)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=5, joint="curve")
    ic.image.alpha_composite(lay)


# ---- parts -------------------------------------------------------------------------------------
LA0, LA1 = (254, 250), (580, 516)  # launder: head at the bank, mouth over the head of the tye
LW = 96
WATER_Y = 742                        # waterline on everything standing in the stream
TX0, TX1 = 492, 900                  # tye (streaming box)
FAR, NEAR, FOOT = 566, 640, 800


def launder_y(x: float) -> float:
    return LA0[1] + (LA1[1] - LA0[1]) * (x - LA0[0]) / (LA1[0] - LA0[0])


def trestles(ic: Icon) -> None:
    """Two clearly separate A-frame trestles standing in the stream under the launder."""
    for x, spread in ((352, 56), (478, 60)):
        top = launder_y(x) + LW * 0.5
        foot = WATER_Y + 40
        timber(ic, (x - 4, top), (x - spread, foot), 24)
        timber(ic, (x + 4, top), (x + spread, foot), 24)
        yb = top + (foot - top) * 0.52
        timber(ic, (x - spread * 0.62, yb), (x + spread * 0.62, yb), 16)
        # cap beam the trough sits on
        timber(ic, (x - 34, top - 4), (x + 34, top + 6), 20, "#9a7048", "#56391f")


def launder(ic: Icon) -> None:
    """Thick open plank trough: far board with a lit top, bright running water, near board."""
    (x0, y0), (x1, y1) = LA0, LA1
    far = [(x0, y0 - LW * 0.62), (x1, y1 - LW * 0.62), (x1, y1 - LW * 0.2), (x0, y0 - LW * 0.2)]
    ic.poly(far, "#6a4c32", "#3e2c1e", edge=0)
    ic.line([(x0, y0 - LW * 0.6), (x1, y1 - LW * 0.6)], 6, (224, 190, 140, 200))  # lit top of the far board
    water = [(x0, y0 - LW * 0.48), (x1, y1 - LW * 0.48), (x1, y1 - LW * 0.12), (x0, y0 - LW * 0.12)]
    wm = ic.poly_mask(water)
    ic.fill(wm, W_RUN, W_RUN_DK, (y0 - LW * 0.5, y1), noise=0.06, chroma=0.02)
    lay, d = layer()
    for t in np.linspace(0.02, 0.96, 16):
        x = x0 + (x1 - x0) * t + ic.random.uniform(-10, 10)
        y = launder_y(x) - LW * ic.random.uniform(0.2, 0.42)
        d.line([(x, y), (x + 36, y + 16)], fill=(245, 252, 255, 220), width=5)
    for t in np.linspace(0.05, 0.9, 7):
        x = x0 + (x1 - x0) * t
        y = launder_y(x) - LW * 0.16
        d.line([(x, y), (x + 50, y + 22)], fill=(20, 70, 130, 110), width=4)
    composite(ic, lay, wm)
    side = [(x0, y0 - LW * 0.14), (x1, y1 - LW * 0.14), (x1, y1 + LW * 0.52), (x0, y0 + LW * 0.52)]
    planks(ic, side, "#a8784a", "#5a3c24", board=22, vertical_boards=False)
    ic.line([(x0, y0 - LW * 0.14), (x1, y1 - LW * 0.14)], 8, (250, 222, 170, 170))  # lit plank top
    ic.shade(ic.poly_mask([(x0, y0 + LW * 0.28), (x1, y1 + LW * 0.28), (x1, y1 + LW * 0.52), (x0, y0 + LW * 0.52)]),
             (22, 14, 8), 0.5, blur=3)  # dark underside
    # end cleats along the trough
    for t in (0.18, 0.5, 0.8):
        x = x0 + (x1 - x0) * t
        y = launder_y(x)
        ic.poly([(x - 9, y - LW * 0.2), (x + 9, y - LW * 0.2), (x + 9, y + LW * 0.56), (x - 9, y + LW * 0.56)],
                "#9a7048", "#4e3420", edge=3)
    ic.outline(side, 4, (40, 26, 16, 200))
    ic.outline([far[0], far[1], side[2], side[3]], 4, (40, 26, 16, 170))


def tye_back(ic: Icon) -> Image.Image:
    """Far wall, end walls and the bed of washed gravel with black tin behind the riffles."""
    planks(ic, [(TX0 + 8, FAR - 30), (TX1 - 8, FAR - 28), (TX1 - 8, FAR + 6), (TX0 + 8, FAR + 6)],
           "#7a5636", "#4a3322", board=44)
    ic.line([(TX0 + 8, FAR - 30), (TX1 - 8, FAR - 28)], 7, (240, 206, 156, 200))
    bed = [(TX0 + 8, FAR + 4), (TX1 - 8, FAR + 6), (TX1, NEAR), (TX0, NEAR)]
    bm = ic.poly_mask(bed)
    ic.fill(bm, "#c8ac80", "#8a7050", (FAR, NEAR), noise=0.28)
    pebbles(ic, bm, 60, (5, 9), tones=((208, 186, 146), (176, 150, 112), (146, 124, 92), (196, 172, 132)), hi=70)
    riffles = (680, 800)
    lay, d = layer()
    R = ic.random
    for cx, n in ((TX0 + 130, 120), (riffles[0] - 30, 80), (riffles[1] - 28, 60)):
        for _ in range(n):
            x = cx + R.gauss(0, 34 if cx == TX0 + 120 else 20)
            y = R.uniform(FAR + 8, NEAR - 6)
            r = R.uniform(2.5, 5.5)
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(24, 20, 20, 240))
            if R.random() < 0.25:
                d.ellipse((x - r * 0.5, y - r * 0.6, x, y - r * 0.2), fill=(220, 220, 214, 200))
    for _ in range(30):  # water sheeting over the bed
        x, y = R.uniform(TX0, TX1 - 40), R.uniform(FAR + 8, NEAR - 6)
        d.line([(x, y), (x + R.uniform(30, 70), y + R.uniform(-2, 2))], fill=(170, 216, 250, 120), width=4)
    composite(ic, lay, bm)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, FAR, SIZE, FAR + 18))), alpha=0.4, blur=6)
    for x in riffles:  # cross-riffles: lit top, shadow downstream
        pts = [(x - 12, FAR + 4), (x + 8, FAR + 4), (x + 14, NEAR), (x - 10, NEAR)]
        ic.shade(ic.poly_mask([(x + 8, FAR + 6), (x + 30, FAR + 6), (x + 38, NEAR), (x + 14, NEAR)]), alpha=0.35, blur=5)
        ic.poly(pts, "#b08658", "#5e4028", (x - 12, x + 14), vertical=False, edge=4)
    # end walls seen edge-on
    for x0, x1 in ((TX0, TX0 + 18), (TX1 - 18, TX1)):
        ic.poly([(x0 + 8, FAR - 30), (x1, FAR - 30), (x1, NEAR + 4), (x0, NEAR + 4)], "#9a7048", "#56391f", edge=4)
    return bm


def tye_front(ic: Icon) -> Image.Image:
    near = [(TX0, NEAR), (TX1, NEAR), (TX1 - 4, FOOT), (TX0 + 4, FOOT)]
    nm = planks(ic, near, "#a47448", "#583a22", board=26, vertical_boards=False)
    ic.shade(ic.intersect(nm, ic.mask("rectangle", (TX0 + 260, 0, SIZE, SIZE))), alpha=0.16, blur=20)
    for x in (TX0 + 16, TX0 + 206, TX1 - 18):
        timber(ic, (x, NEAR - 28), (x, FOOT + 6), 26, "#946a44", "#4a3220")
    ic.line([(TX0, NEAR + 2), (TX1, NEAR + 2)], 8, (250, 224, 176, 190))  # lit top edge
    ic.outline(near, 4, (40, 26, 16, 200))
    return ic.poly_mask([(TX0 - 30, NEAR - 40), (TX1 + 10, NEAR - 40), (TX1 + 10, FOOT + 40), (TX0 - 30, FOOT + 40)])


def fall(ic: Icon) -> None:
    """Water pouring off the launder mouth as a sheet into the head of the box, with a splash."""
    mx, my = LA1[0], LA1[1] - LW * 0.46
    bottom = FAR + 40
    lay, d = layer()
    sheet = [(mx - 2, my), (mx + 16, my - 2), (mx + 44, my + 30), (mx + 54, bottom), (mx + 6, bottom + 4),
             (mx - 4, my + 40)]
    d.polygon(sheet, fill=(110, 180, 236, 240))
    for k in range(6):
        x = mx + k * 8
        d.line([(x, my + 2), (x + 10 + k * 3, my + 34), (x + 14 + k * 4, bottom)], fill=(236, 248, 255, 225),
               width=4 if k % 2 else 6, joint="curve")
    ic.image.alpha_composite(lay)
    lay, d = layer()
    R = ic.random
    for _ in range(18):  # splash crown on the bed
        r = R.uniform(5, 11)
        sx, sy = mx + 30 + R.uniform(-54, 64), bottom + R.uniform(-14, 10)
        d.ellipse((sx - r * 1.3, sy - r * 0.7, sx + r * 1.3, sy + r * 0.7), fill=(236, 248, 255, 225))
    for _ in range(10):  # drops thrown up
        r = R.uniform(3, 6)
        sx, sy = mx + 30 + R.uniform(-60, 70), bottom - R.uniform(18, 46)
        d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(232, 246, 255, 210))
    ic.image.alpha_composite(lay)


def shovel(ic: Icon, top, blade) -> None:
    """Long shovel leaning on the box: handle with a crutch grip, iron blade on the gravel."""
    tx, ty = top
    bx, by = blade
    timber(ic, top, blade, 14, "#b08a5e", "#6a4a2c")
    ic.line([(tx - 18, ty - 4), (tx + 18, ty + 6)], 12, (60, 40, 24))
    ic.line([(tx - 16, ty - 5), (tx + 16, ty + 4)], 6, (170, 130, 86))
    a = math.degrees(math.atan2(by - ty, bx - tx)) - 90
    pts = ic.rotate([(-24, -6), (24, -6), (22, 44), (0, 58), (-22, 44)], (bx, by), a)
    ic.poly(pts, "#9a9894", "#4a4846", edge=4)
    ic.line(ic.rotate([(-18, 0), (-16, 38)], (bx, by), a), 4, (240, 240, 236, 160))


def bank(ic: Icon) -> None:
    """Small turf-capped gravel bank in the left quarter, lighter pebbles, dark wet foot."""
    pts = [(34, 800), (40, 736), (58, 680), (70, 610), (98, 560), (112, 480), (140, 420), (152, 344), (184, 270),
           (230, 226), (270, 236), (300, 300), (322, 420), (334, 580), (332, 740), (306, 810)]
    bm = ic.poly_mask(pts)
    ic.fill(bm, "#c8a26c", "#6e5234", radial=(170, 260, 620), noise=0.3, chroma=0.14)
    pebbles(ic, bm, 150, (5, 11), tones=((226, 202, 160), (190, 160, 118), (150, 118, 84), (208, 180, 138)), hi=130)
    ic.shade(ic.intersect(bm, ic.mask("rectangle", (0, 640, SIZE, SIZE))), (24, 30, 34), 0.5, blur=26)  # wet foot
    ic.outline(pts)
    turf = ic.intersect(bm, ic.poly_mask([(0, 0), (SIZE, 0), (SIZE, 330), (290, 360), (240, 350), (190, 392),
                                          (150, 450), (100, 560), (0, 590)]))
    ic.fill(turf, "#a8bc56", "#5a7424", radial=(200, 220, 260), noise=0.3, chroma=0.16)
    lay, d = layer()
    for _ in range(80):
        x, y = ic.random.uniform(60, 320), ic.random.uniform(200, 480)
        h = ic.random.uniform(10, 22)
        col = (ic.random.randint(70, 150), ic.random.randint(96, 160), ic.random.randint(40, 70), 150)
        d.line([(x, y), (x + ic.random.uniform(-6, 6), y - h)], fill=col, width=4)
    composite(ic, lay, turf)
    lip = ImageChops.subtract(turf.filter(ImageFilter.MaxFilter(15)), turf)
    ic.shade(ic.intersect(lip, bm), (40, 30, 20), 0.5, blur=4)
    with ic.clipped(bm):
        for x, y, w in ((170, 262, 50), (226, 230, 60), (270, 244, 30), (120, 380, 30)):
            tufts(ic, x, y, w)
    ic.waterline(bm, WATER_Y)


def heap(ic: Icon) -> None:
    """Cassiterite heap on a light gravel spit, with glinting facets."""
    spit = [(740, 836), (770, 776), (960, 764), (1004, 820), (960, 858), (780, 862)]
    ic.poly(spit, "#c8b490", "#7e6a50", noise=0.3, edge=4)
    pebbles(ic, ic.poly_mask(spit), 60, tones=((220, 206, 176), (188, 170, 140), (150, 134, 110)), hi=120)
    ic.heap(756, 1000, 830, 566, 34, 7, body=("#5a4a40", "#221a16"), lump=(TIN, TIN_DK),
            odd=("#9a8670", "#43362a"), odd_share=0.2)
    R = ic.random
    lay, d = layer()
    for _ in range(16):  # greasy adamantine lustre on a few crystal faces
        t = R.random()
        y = 610 + (810 - 610) * t
        half = 124 * (0.2 + 0.7 * t)
        x = 878 + R.uniform(-half, half)
        r = R.uniform(3, 7)
        a = R.uniform(0, 6.28)
        d.polygon([(x + math.cos(a) * r, y + math.sin(a) * r), (x + math.cos(a + 2.2) * r * 0.6, y + math.sin(a + 2.2) * r * 0.6),
                   (x + math.cos(a + 3.9) * r * 0.8, y + math.sin(a + 3.9) * r * 0.8)], fill=(238, 234, 226, R.randint(150, 220)))
    ic.image.alpha_composite(lay)


def draw(ic: Icon) -> None:
    ic.water_band(top=676, bottom=808, x0=24, x1=1000, inset=34, sag=34, light=W_LIGHT, deep=W_DEEP)
    bank(ic)
    # head box at the top of the bank the launder draws from
    ic.poly([(226, 212), (284, 206), (288, 304), (230, 310)], "#8a6444", "#4a3222", edge=4)
    ic.shade(ic.poly_mask([(264, 208), (284, 206), (288, 304), (268, 306)]), alpha=0.3)
    tye_back(ic)
    trestles(ic)
    # cast shadow of the launder on the water and the bank below it
    ic.shade(ic.poly_mask([(LA0[0], LA0[1] + 80), (LA1[0], LA1[1] + 80), (LA1[0], LA1[1] + 130),
                           (LA0[0], LA0[1] + 130)]), alpha=0.25, blur=16)
    launder(ic)
    fall(ic)
    zone = tye_front(ic)
    trestle_legs = ic.mask("rectangle", (280, 600, 560, 800))
    ic.waterline(ImageChops.lighter(zone, trestle_legs), WATER_Y)
    ic.foam(290, 560, WATER_Y + 2)
    ic.foam(470, 920, WATER_Y + 2)
    heap(ic)
    shovel(ic, (650, 452), (774, 812))
