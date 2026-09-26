"""Tin Stamping Mill (tin_stamping_mill): water-powered stamps crushing lode tin.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/tin_stamping_mill/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tin_stamping_mill

Identity: an overshot water wheel on the left, fed by the same kind of plank launder as the
streamworks (water breaking off its end onto the top of the wheel), turns a dark cam axle straight
into an open-fronted shingled shed where a battery of four dark timber stamps with bright iron heads,
lifted to staggered heights, stands over a lit mortar box spilling pale crushed ore; black tin runs
out to a heap on the right. Tier 1 of the tin chain: the streamworks' launder and black ore, plus wheel, roof and
machinery. The vanilla sawmill has its wheel on the right and a saw; this one reads through the
row of stamps.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 37
REFS = ("sawmill", "lumber_mill", "stannary_court", "irrigation_systems")

WOOD, WOOD_DK = "#8a6240", "#4e3522"
W_LIGHT, W_DEEP = "#3c98e0", "#0c4892"    # stream: same vanilla-like blue as the streamworks
W_RUN, W_RUN_DK = "#bfe6ff", "#4c9ad8"    # water running in the launder
TIN, TIN_DK = "#806654", "#241a14"
IRON, IRON_DK = "#6e6c6a", "#2a2828"


# ---- helpers (copied from canal_lock_works / tin_streamworks, candidates for the kit) -----------
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


def post(ic: Icon, x: float, y0: float, y1: float, w: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Upright square timber: lit left face, shaded right face."""
    m = ic.mask("rectangle", (x - w / 2, y0, x + w / 2, y1))
    ic.fill(m, c1, c2, (x - w / 2, x + w / 2), vertical=False, noise=0.18)
    ic.line([(x - w * 0.3, y0 + 3), (x - w * 0.3, y1 - 3)], 3, (255, 228, 190, 80))
    ic.outline([(x - w / 2, y0), (x + w / 2, y0), (x + w / 2, y1), (x - w / 2, y1)], 4, (40, 26, 16, 180))


def ring(ic: Icon, cx: float, cy: float, r0: float, r1: float) -> Image.Image:
    outer = ic.mask("ellipse", (cx - r1, cy - r1, cx + r1, cy + r1))
    inner = ic.mask("ellipse", (cx - r0, cy - r0, cx + r0, cy + r0))
    return ImageChops.subtract(outer, inner)


def shingles(ic: Icon, left_eave, right_eave, right_ridge, left_ridge, sag: float, c1, c2) -> Image.Image:
    """Shingle roof plane with irregular courses: varied course height and tile width, offset joints,
    a few darker and mossy tiles, a slightly sagging ridge. Returns the roof mask."""
    R = ic.random
    (lx0, ey), (rx0, _) = left_eave, right_eave
    (rx1, ry), (lx1, _) = right_ridge, left_ridge
    ts = np.linspace(0, 1, 16)
    ridge = [(rx1 + (lx1 - rx1) * t, ry + sag * math.sin(math.pi * t)) for t in ts]
    pts = [left_eave, right_eave] + ridge
    rm = ic.poly_mask(pts)
    ic.fill(rm, c1, c2, (ry, ey), noise=0.22, chroma=0.12)

    def sag_at(x: float, v: float) -> float:
        u = min(max((x - lx1) / (rx1 - lx1), 0), 1)
        return sag * math.sin(math.pi * u) * (1 - v)

    lay, d = layer()
    y = ry - 6
    while y < ey:
        h = R.uniform(24, 40)
        v0, v1 = (y - ry) / (ey - ry), (y + h - ry) / (ey - ry)
        xl = lx1 + (lx0 - lx1) * max(v0, 0) - 30
        xr = rx1 + (rx0 - rx1) * min(v1, 1) + 30
        x = xl - R.uniform(0, 40)
        while x < xr:
            w = R.uniform(28, 64)
            a, b = x, x + w - 2
            tilt = R.uniform(-4, 4)
            quad = [(a, y + sag_at(a, v0)), (b, y + sag_at(b, v0)), (b + R.uniform(-3, 3), y + h + tilt + sag_at(b, v1)),
                    (a + R.uniform(-3, 3), y + h - tilt + sag_at(a, v1))]
            roll = R.random()
            if roll < 0.08:
                col = (30, 22, 16, R.randint(70, 110))        # dark, rotten shingle
            elif roll < 0.15:
                col = (96, 118, 48, R.randint(90, 140))       # moss
            elif roll < 0.55:
                col = (255, 236, 204, R.randint(10, 46))      # sun-bleached
            else:
                col = (40, 26, 16, R.randint(10, 50))
            d.polygon(quad, fill=col)
            d.line([quad[3], quad[2]], fill=(34, 22, 14, 170), width=5)          # overlap shadow
            d.line([quad[0], quad[3]], fill=(34, 22, 14, R.randint(70, 130)), width=3)  # joint
            d.line([quad[0], quad[1]], fill=(255, 238, 206, 50), width=2)        # lit butt edge
            x += w
        y += h
    composite(ic, lay, rm)
    return rm


# ---- parts -------------------------------------------------------------------------------------
WX, WY, WR = 262, 520, 196  # water wheel
AXLE_Y = WY
WATER_Y = 704


def wheel(ic: Icon) -> None:
    """Overshot wheel: far rim in shadow, buckets, spokes, near rim, iron-banded hub."""
    R = ic.random
    far = ring(ic, WX + 22, WY - 10, WR - 30, WR)
    ic.fill(far, "#5a3e28", "#34241a", (WY - WR, WY + WR), noise=0.2)
    # buckets between the rims, seen edge-on
    for k in range(18):
        a = k * 20 + R.uniform(-2, 2)
        pts = ic.rotate([(-16, WR - 34), (16, WR - 34), (18, WR + 2), (-18, WR + 2)], (WX + 10, WY - 5), a)
        ic.poly(pts, "#7a5638", "#46301e", edge=4)
    for k in range(8):
        a = math.radians(k * 45 + 10)
        timber(ic, (WX + math.cos(a) * 30, WY + math.sin(a) * 30),
               (WX + math.cos(a) * (WR - 20), WY + math.sin(a) * (WR - 20)), 22, "#8e6644", "#523823")
    near = ring(ic, WX, WY, WR - 30, WR)
    ic.fill(near, "#9a7048", "#4e3522", radial=(WX - WR * 0.7, WY - WR * 0.7, WR * 2.2), noise=0.2)
    lay, d = layer()
    for k in range(18):  # rim joints
        a = math.radians(k * 20 + 5)
        d.line([(WX + math.cos(a) * (WR - 30), WY + math.sin(a) * (WR - 30)),
                (WX + math.cos(a) * WR, WY + math.sin(a) * WR)], fill=(40, 26, 16, 150), width=4)
    d.arc((WX - WR + 6, WY - WR + 6, WX + WR - 6, WY + WR - 6), 190, 290, fill=(255, 230, 190, 90), width=5)
    composite(ic, lay, near)
    ic.overlay(lambda d: (d.ellipse((WX - WR, WY - WR, WX + WR, WY + WR), outline=(40, 26, 16, 200), width=5),
                          d.ellipse((WX - WR + 30, WY - WR + 30, WX + WR - 30, WY + WR - 30),
                                    outline=(40, 26, 16, 200), width=4)))
    # wet darkening low on the wheel
    wm = ImageChops.lighter(near, far)
    ic.shade(ic.intersect(wm, ic.mask("rectangle", (0, WY + 60, SIZE, SIZE))), (20, 30, 34), 0.3, blur=20)


def hub(ic: Icon) -> None:
    ic.ellipse((WX - 42, WY - 42, WX + 42, WY + 42), "#6a4c34", "#2e1e12")
    ic.overlay(lambda d: d.ellipse((WX - 32, WY - 32, WX + 32, WY + 32), outline=(52, 50, 50, 255), width=8))
    ic.ellipse((WX - 13, WY - 13, WX + 13, WY + 13), IRON, IRON_DK, edge=3)


LX0, LX1, LY = 34, WX + 34, 262  # launder


def launder(ic: Icon) -> None:
    """Plank launder on a trestle bringing water over the top of the wheel."""
    x0, x1, y = LX0, LX1, LY
    inner = [(x0, y - 40), (x1, y - 38), (x1, y - 14), (x0, y - 16)]
    ic.poly(inner, "#6a4c32", "#3e2c1e", edge=0)
    ic.line([(x0, y - 39), (x1, y - 37)], 6, (224, 190, 140, 200))
    wm = ic.poly_mask([(x0, y - 32), (x1, y - 30), (x1, y - 12), (x0, y - 14)])
    ic.fill(wm, W_RUN, W_RUN_DK, (y - 34, y - 10), noise=0.06, chroma=0.02)
    ic.overlay(lambda d: [d.line([(x, y - 24), (x + 30, y - 23)], fill=(245, 252, 255, 220), width=4)
                          for x in range(x0 + 10, x1 - 20, 50)], wm)
    planks(ic, [(x0, y - 14), (x1, y - 12), (x1, y + 34), (x0, y + 32)], "#a8784a", "#5a3c24", board=16,
           vertical_boards=False)
    ic.line([(x0, y - 14), (x1, y - 12)], 7, (250, 222, 170, 170))
    ic.shade(ic.poly_mask([(x0, y + 18), (x1, y + 20), (x1, y + 34), (x0, y + 32)]), (22, 14, 8), 0.45)
    ic.outline([(x0, y - 40), (x1, y - 38), (x1, y + 34), (x0, y + 32)], 4, (40, 26, 16, 190))


def water_on_wheel(ic: Icon) -> None:
    """Water breaking off the launder end onto the top of the wheel: short uneven sheet and drops."""
    R = ic.random
    mx, my = LX1, LY - 30
    land = WY - WR + 14
    lay, d = layer()
    sheet = [(mx - 4, my), (mx + 10, my - 2), (mx + 34, my + 20), (mx + 48, land + 6), (mx + 30, land + 16),
             (mx + 14, land + 4), (mx + 2, land + 12), (mx - 6, my + 30)]
    d.polygon(sheet, fill=(110, 180, 236, 235))
    for k, (dx, w) in enumerate(((0, 6), (10, 4), (18, 6), (28, 4), (38, 5))):
        end = land + R.uniform(-4, 10)
        d.line([(mx + dx * 0.4, my + 2), (mx + dx * 0.7 + 8, my + 30), (mx + dx + 6, end)], fill=(236, 248, 255, 225),
               width=w, joint="curve")
    for _ in range(14):  # drops breaking off the sheet and off the buckets
        r = R.uniform(3, 7)
        sx, sy = mx + R.uniform(-10, 50), R.uniform(my + 30, land + 60)
        d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(232, 246, 255, 215))
    for _ in range(10):  # splash where it lands on the buckets
        r = R.uniform(5, 9)
        sx, sy = mx + 24 + R.uniform(-30, 40), land + R.uniform(0, 18)
        d.ellipse((sx - r * 1.3, sy - r * 0.7, sx + r * 1.3, sy + r * 0.7), fill=(236, 248, 255, 225))
    ic.image.alpha_composite(lay)


def launder_trestle(ic: Icon) -> None:
    """Open A-frame trestle under the launder, sky between the legs."""
    x, top = 110, LY + 34
    timber(ic, (x - 4, top), (x - 76, 740), 22, "#ae845a", "#6a4a2e")
    timber(ic, (x + 4, top), (x + 70, 740), 22, "#ae845a", "#6a4a2e")
    timber(ic, (x - 50, 560), (x + 48, 560), 14, "#ae845a", "#6a4a2e")


HX0, HX1 = 450, 960      # mill shed
EAVE, RIDGE = 396, 196
FLOOR = 742


def shed(ic: Icon) -> None:
    """Open-fronted shed: warm grey back wall boards so the dark stems stand out."""
    back = planks(ic, [(HX0, EAVE - 30), (HX1, EAVE - 30), (HX1, FLOOR), (HX0, FLOOR)], "#a08a70", "#665440", board=34)
    ic.shade(ic.intersect(back, ic.mask("rectangle", (0, EAVE - 30, SIZE, EAVE + 90))), alpha=0.35, blur=24)
    ic.shade(ic.intersect(back, ic.mask("rectangle", (840, 0, SIZE, SIZE))), alpha=0.18, blur=20)


def roof(ic: Icon) -> None:
    rm = shingles(ic, (HX0 - 44, EAVE + 6), (HX1 + 34, EAVE + 6), (HX1 - 6, RIDGE), (HX0 + 12, RIDGE), 12,
                  "#a48c6c", "#5e4a34")
    R = ic.random
    for _ in range(5):  # moss patches low on the roof
        blob = ic.poly_mask(ic.jitter(R.uniform(HX0, HX1), R.uniform(EAVE - 90, EAVE - 10), R.uniform(20, 46), 14, 9, 0.3))
        ic.shade(ic.intersect(rm, blob), (96, 112, 50), R.uniform(0.2, 0.35), blur=5)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (0, EAVE - 60, SIZE, EAVE + 10))), alpha=0.22, blur=16)
    ic.line([(HX0 - 44, EAVE + 6), (HX1 + 34, EAVE + 6)], 10, (70, 50, 34))
    ic.outline([(HX0 - 44, EAVE + 6), (HX1 + 34, EAVE + 6), (HX1 - 6, RIDGE), (HX0 + 12, RIDGE)], 6)


STEMS = ((552, 560), (624, 604), (696, 538), (768, 584))  # (x, head top): heads staggered by the cams
HEAD_H = 100
BOX_TOP = 704


def stamps(ic: Icon) -> None:
    # frame: two uprights, top guide
    post(ic, 494, EAVE - 20, FLOOR, 34)
    post(ic, 826, EAVE - 20, FLOOR, 34)
    timber(ic, (478, 428), (842, 428), 22)
    # cam axle: dark, from the wheel hub straight into the shed
    timber(ic, (WX, AXLE_Y), (846, AXLE_Y), 40, "#4e3826", "#1e140c")
    ic.line([(WX + 50, AXLE_Y - 12), (846, AXLE_Y - 12)], 4, (200, 170, 130, 90))
    for x, _ in STEMS:  # iron bands and cams on the axle
        ic.line([(x - 40, AXLE_Y - 20), (x - 40, AXLE_Y + 20)], 6, (70, 68, 66))
        ic.poly([(x - 30, AXLE_Y - 18), (x - 14, AXLE_Y - 36), (x - 10, AXLE_Y + 6)], "#6a4a30", "#2e1e12", edge=4)
    for x, head in STEMS:
        post(ic, x, 400, head + 6, 36, "#6a4a30", "#2a1c10")
        tap = head - 64
        ic.rect((x - 30, tap - 22, x + 24, tap), "#8a6444", "#3e2a1a", edge=4)  # tappet
        # iron head shod on the stem foot: bright face, specular top edge, dark underside
        hx0, hx1 = x - 25, x + 25
        ic.rect((hx0, head, hx1, head + HEAD_H), "#b2b0aa", "#3e3c3a", vertical=False, edge=5)
        ic.line([(hx0 + 3, head + 4), (hx1 - 3, head + 4)], 5, (252, 252, 246, 230))
        ic.line([(hx0 + 7, head + 10), (hx0 + 7, head + HEAD_H - 12)], 4, (240, 240, 234, 120))
        ic.shade(ic.mask("rectangle", (hx0, head + HEAD_H - 22, hx1, head + HEAD_H)), alpha=0.45)
    timber(ic, (478, 470), (842, 470), 18)  # guide just above the axle, in front of the stems
    # mortar box with pale crushed ore spilling over its lip and out at its feet
    box = [(476, BOX_TOP), (838, BOX_TOP), (834, FLOOR + 24), (480, FLOOR + 24)]
    planks(ic, box, "#b8885a", "#6a4628", board=20, vertical_boards=False)
    ic.line([(476, BOX_TOP), (838, BOX_TOP)], 7, (255, 232, 190, 170))
    ic.outline(box, 4, (40, 26, 16, 190))
    for x, head in STEMS:  # contact shadow of the dropped heads on the ore bed
        ic.shade(ic.mask("ellipse", (x - 40, BOX_TOP - 10, x + 40, BOX_TOP + 8)), alpha=0.3 if head > 600 else 0.12,
                 blur=6)
    R = ic.random
    bed = [(484, BOX_TOP - 14), (830, BOX_TOP - 16), (834, BOX_TOP + 2), (480, BOX_TOP + 2)]
    ic.poly(bed, "#dcd4c4", "#9a9284", noise=0.3, edge=3)
    spill = [(470, FLOOR + 40), (500, FLOOR + 20), (620, FLOOR + 14), (780, FLOOR + 18), (850, FLOOR + 30), (830, FLOOR + 50),
             (500, FLOOR + 52)]
    sm = ic.poly_mask(spill)
    ic.fill(sm, "#d8d0c0", "#8c8478", (FLOOR - 4, FLOOR + 46), noise=0.3)
    lay, d = layer()
    for _ in range(90):
        x, y = R.uniform(480, 850), R.uniform(FLOOR + 14, FLOOR + 50)
        r = R.uniform(3, 6)
        c = R.choice(((236, 230, 220), (150, 144, 136), (60, 54, 50)))
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=c + (200,))
    composite(ic, lay, sm)
    ic.outline(spill, 4)


def ore_heap(ic: Icon) -> None:
    # dressing trough carrying the crushed tin out of the box
    timber(ic, (830, 726), (890, 750), 26, "#8a6444", "#4a3220")
    ic.heap(806, 1004, 810, 570, 32, 7, body=("#5a4a40", "#221a16"), lump=(TIN, TIN_DK),
            odd=("#b0a288", "#5e5440"), odd_share=0.14)


def draw(ic: Icon) -> None:
    band = ic.water_band(top=700, bottom=800, x0=20, x1=1004, inset=30, sag=30, light=W_LIGHT, deep=W_DEEP)
    shed(ic)
    launder_trestle(ic)
    wheel(ic)
    stamps(ic)
    hub(ic)
    roof(ic)
    # the roof shades the top of the machinery and the back wall
    ic.shade(ic.mask("rectangle", (HX0, EAVE + 10, HX1, EAVE + 70)), alpha=0.35, blur=18)
    launder(ic)
    water_on_wheel(ic)
    ore_heap(ic)
    hull = ring(ic, WX, WY, 0, WR + 40)
    ic.waterline(ImageChops.lighter(hull, ic.mask("rectangle", (20, 690, 200, 780))), WATER_Y)
    # churned foam where the wheel dips into the stream
    lay, d = layer()
    R = ic.random
    for _ in range(26):
        r = R.uniform(6, 14)
        sx, sy = R.uniform(WX - 150, WX + 190), WATER_Y + R.uniform(-8, 16)
        d.ellipse((sx - r * 1.6, sy - r * 0.6, sx + r * 1.6, sy + r * 0.6), fill=(240, 248, 255, 225))
    for _ in range(10):
        r = R.uniform(3, 6)
        sx, sy = R.uniform(WX - 40, WX + 200), WATER_Y - R.uniform(10, 40)
        d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(236, 248, 255, 200))
    ic.image.alpha_composite(lay)
    ic.foam(30, 470, WATER_Y + 4)
