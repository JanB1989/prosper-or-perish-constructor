"""Gold Diggings (gold_diggings): alluvial workings on a gravel bank above a stream.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/gold_diggings/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/gold_diggings

Identity: a big hand windlass (squared posts, rope drum, crank, bucket over the shaft) lit against
the dark back bank, a pale spoil cone on the left, a wooden sluice trough with bright water from its
head box down into a white splash in the stream, and a tilted gold pan with a few bright flakes
propped against the cut gravel face. No building: the tier-1 gold_stamp_mill adds the mill house.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 57
REFS = ("sand_pit", "clay_pit", "schwaz_mine", "sawmill")

GRAVEL, GRAVEL_DK = "#c8a86c", "#8e6c40"
EARTH, EARTH_DK = "#8a6a44", "#4a3420"
W_LIGHT, W_DEEP = "#7cb6c6", "#2a5c6e"
WOOD, WOOD_DK = "#8e6640", "#4e3522"
GOLD, GOLD_DK = "#f6cc50", "#9a6a14"
DARK = (28, 18, 12)
IRON = (52, 50, 50)


# ---------------------------------------------------------------- helpers (copied / new)
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
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half (from canal_lock_works)."""
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
    ic.shade(ic.poly_mask(lower), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def spout(ic: Icon, x: float, y: float, dx: float, dy: float, w: float = 16) -> None:
    """Water jet leaving an opening at (x, y), arcing by (dx, dy), with a splash (from canal_lock_works)."""
    ts = np.linspace(0, 1, 18)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    lay, d = layer()
    d.line(path, fill=(170, 210, 220, 230), width=int(w + 8), joint="curve")
    d.line(path, fill=(236, 246, 247, 240), width=int(w), joint="curve")
    d.line([(px - 2, py - w * 0.2) for px, py in path[2:]], fill=(255, 255, 255, 170), width=max(3, int(w * 0.3)))
    ex, ey = path[-1]
    for _ in range(14):
        r = ic.random.uniform(4, 10)
        sx, sy = ex + ic.random.uniform(-w * 2.2, w * 2.2), ey + ic.random.uniform(-w * 1.2, w * 0.4)
        d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(240, 248, 248, 210))
    d.ellipse((ex - w * 2.6, ey - w * 0.5, ex + w * 2.6, ey + w * 0.7), fill=(232, 244, 245, 200))
    ic.image.alpha_composite(lay)


def glints(ic: Icon, pts, r: float = 7, color=(255, 246, 200)) -> None:
    """Small metallic sparkles: a bright dot with a short cross (new)."""
    lay, d = layer()
    for x, y in pts:
        d.line([(x - r * 1.8, y), (x + r * 1.8, y)], fill=color + (150,), width=3)
        d.line([(x, y - r * 1.8), (x, y + r * 1.8)], fill=color + (150,), width=3)
        d.ellipse((x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7), fill=color + (235,))
    composite(ic, lay)


def pebbles(ic: Icon, clip: Image.Image, box, n: int, rmin: float = 6, rmax: float = 16) -> None:
    """Gravel: scattered small stones, each lit top-left with a contact shadow, kept inside ``clip`` (new)."""
    x0, y0, x1, y1 = box
    lay, d = layer()
    R = ic.random
    for _ in range(n):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        r = R.uniform(rmin, rmax) * (0.6 + 0.4 * (y - y0) / max(y1 - y0, 1))
        base = R.choice([(170, 150, 120), (150, 140, 128), (190, 170, 130), (120, 104, 86), (200, 190, 170)])
        d.ellipse((x - r + 3, y - r * 0.6 + 4, x + r + 3, y + r * 0.6 + 4), fill=(30, 20, 10, 110))
        d.ellipse((x - r, y - r * 0.65, x + r, y + r * 0.65), fill=base + (255,))
        d.ellipse((x - r * 0.6, y - r * 0.55, x + r * 0.2, y - r * 0.05), fill=(255, 248, 230, 90))
    composite(ic, lay, clip)


def gold_pan(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> None:
    """Shallow dark iron pan seen from above: sloping rim, wet black sand and bright gold flakes (new)."""
    ic.fill(ic.mask("ellipse", (cx - rx + 10, cy - ry + 14, cx + rx + 14, cy + ry + 18)), (40, 30, 20), (40, 30, 20),
            noise=0.05)  # contact shadow
    ic.fill(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), "#6a625c", "#2e2a28",
            radial=(cx - rx * 0.5, cy - ry * 0.8, rx * 2.0), noise=0.14)
    inner = (cx - rx * 0.78, cy - ry * 0.68, cx + rx * 0.78, cy + ry * 0.78)
    ic.fill(ic.mask("ellipse", inner), "#38342f", "#56504a", radial=(cx + rx * 0.2, cy + ry * 0.3, rx * 0.9), noise=0.2)
    ic.shade(ic.mask("ellipse", (cx - rx * 0.78, cy - ry * 0.68, cx + rx * 0.78, cy - ry * 0.1)), alpha=0.35, blur=6)
    # a tail of gold at the low side of the pan
    lay, d = layer()
    R = ic.random
    for _ in range(46):
        a = R.uniform(0.1, 0.9) * math.pi
        rr = R.uniform(0.25, 0.6)
        x, y = cx + math.cos(a) * rx * rr * 0.9 - rx * 0.1, cy + math.sin(a) * ry * rr * 0.9
        s = R.uniform(6, 13)
        d.ellipse((x - s, y - s * 0.7, x + s, y + s * 0.7), fill=(246, 204, 80, 255))
        d.ellipse((x - s * 0.5, y - s * 0.6, x + s * 0.1, y - s * 0.1), fill=(255, 246, 200, 200))
    composite(ic, lay, ic.mask("ellipse", inner))
    ic.overlay(lambda d: d.arc((cx - rx + 4, cy - ry + 4, cx + rx - 4, cy + ry - 4), 150, 290,
                               fill=(220, 210, 196, 150), width=5))
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(30, 24, 20, 220), width=5))
    glints(ic, [(cx - rx * 0.1, cy + ry * 0.3), (cx + rx * 0.3, cy + ry * 0.15)], 7)


def weeds(ic: Icon, x: float, y: float, w: float) -> None:
    """Tuft of grass (from canal_lock_works)."""
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(16, 38)
        tip = (bx + R.uniform(-12, 12), y - h)
        col = (R.randint(90, 130), R.randint(110, 140), R.randint(50, 70), 230)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=4, joint="curve")
    ic.image.alpha_composite(lay)


# ---------------------------------------------------------------- parts
def post(ic: Icon, x: float, top: float, base: float, w: float = 34) -> None:
    """Squared timber post seen front-on: lit left face, dark right face, end grain on top (new)."""
    ic.rect((x - w / 2, top, x + w / 2, base), "#dcac74", "#9a6c40", edge=0, noise=0.18)
    ic.shade(ic.mask("rectangle", (x + w * 0.12, top, x + w / 2, base)), (24, 12, 4), 0.5)
    ic.line([(x - w / 2 + 5, top + 6), (x - w / 2 + 5, base - 6)], 3, (255, 232, 190, 120))
    for yy in np.arange(top + 30, base - 20, 46):
        ic.line([(x - w * 0.3, yy), (x - w * 0.1, yy + 18)], 2, (70, 44, 22, 120))
    ic.outline([(x - w / 2, top), (x + w / 2, top), (x + w / 2, base), (x - w / 2, base)], 5)


def windlass(ic: Icon, x0: float, x1: float, top: float, base: float, pit_y: float) -> None:
    """The hero: hand windlass over the shaft. Two thick squared posts with raking braces, a big drum
    wound with rope, an iron crank with a wooden handle, and a bucket hanging over the pit."""
    # raking braces behind the posts
    for x, s in ((x0, -1), (x1, 1)):
        timber(ic, (x + s * 64, base + 4), (x + s * 6, top + 110), 24, "#c8965e", "#6a4628")
    post(ic, x0, top, base, 38)
    post(ic, x1, top, base, 38)
    # cross sill low between the posts
    timber(ic, (x0 + 16, base - 70), (x1 - 16, base - 66), 18, "#a87c50", "#5a3c22")
    # drum (a horizontal log) resting in notches at the post tops
    dy = top + 36
    r = 34
    drum = (x0 - 14, dy - r, x1 + 14, dy + r)
    ic.fill(ic.mask("rectangle", drum), "#b08458", "#4a3220", (dy - r, dy + r), noise=0.18)
    ic.shade(ic.mask("rectangle", (drum[0], dy + r * 0.2, drum[2], drum[3])), (20, 10, 4), 0.35)
    ic.line([(drum[0], dy - r * 0.55), (drum[2], dy - r * 0.55)], 5, (255, 234, 196, 120))
    # rope wound round the middle of the drum
    rx0, rx1 = x0 + 50, x1 - 50
    ic.fill(ic.mask("rectangle", (rx0, dy - r - 2, rx1, dy + r + 2)), "#d8c090", "#8a7048", (dy - r, dy + r), noise=0.2)
    for x in np.arange(rx0 + 4, rx1, 11):
        ic.line([(x, dy - r), (x + 7, dy + r)], 3, (80, 60, 34, 210))
    ic.shade(ic.mask("rectangle", (rx0, dy + r * 0.2, rx1, dy + r + 2)), (20, 10, 4), 0.3)
    for ex in (drum[0], drum[2]):
        ic.ellipse((ex - 10, dy - r, ex + 10, dy + r), "#c8a070", "#7a5836", edge=4)
    ic.outline([(drum[0], drum[1]), (drum[2], drum[1]), (drum[2], drum[3]), (drum[0], drum[3])], 5)
    # iron crank on the right end, handle held out towards the viewer
    ic.line([(x1 + 14, dy), (x1 + 46, dy)], 16, DARK)
    ic.line([(x1 + 14, dy), (x1 + 46, dy)], 10, IRON)
    ic.line([(x1 + 46, dy), (x1 + 58, dy + 70)], 18, DARK)
    ic.line([(x1 + 46, dy), (x1 + 58, dy + 70)], 11, (70, 68, 68))
    ic.line([(x1 + 52, dy + 72), (x1 + 92, dy + 76)], 22, DARK)
    ic.line([(x1 + 52, dy + 72), (x1 + 92, dy + 76)], 14, (150, 108, 66))
    ic.line([(x1 + 56, dy + 68), (x1 + 88, dy + 71)], 4, (255, 230, 190, 120))
    # rope down to a bucket hanging over the pit
    mx = (x0 + x1) / 2 + 14
    by0, by1 = pit_y - 150, pit_y - 72
    ic.line([(mx, dy + r), (mx, by0 - 30)], 8, (60, 44, 26))
    ic.line([(mx - 2, dy + r), (mx - 2, by0 - 30)], 4, (206, 184, 136))
    ic.overlay(lambda d: d.arc((mx - 36, by0 - 34, mx + 36, by0 + 30), 180, 360, fill=IRON + (255,), width=6))
    ic.poly([(mx - 38, by0), (mx + 38, by0), (mx + 30, by1), (mx - 30, by1)], "#a07448", "#553a22", noise=0.2, edge=5)
    ic.shade(ic.poly_mask([(mx + 8, by0), (mx + 38, by0), (mx + 30, by1), (mx + 6, by1)]), (20, 10, 4), 0.35)
    for f in (0.22, 0.78):
        y = by0 + (by1 - by0) * f
        ic.line([(mx - 37 + 8 * f, y), (mx + 37 - 8 * f, y)], 7, IRON)
    ic.ellipse((mx - 38, by0 - 10, mx + 38, by0 + 10), "#b89868", "#6a5030", edge=4)
    ic.shade(ic.mask("ellipse", (mx - 30, pit_y - 30, mx + 50, pit_y - 6)), alpha=0.35, blur=8)


def sluice(ic: Icon, head, mouth, depth: float = 46, far: float = 30) -> tuple[float, float]:
    """Wooden sluice trough on trestles falling to the right: dark side boards, bright water along
    its whole length, dark riffle bars, a head box at the top. Returns the mouth point."""
    (hx, hy), (mx, my) = head, mouth
    for t in (0.18, 0.55, 0.88):
        x, y = hx + (mx - hx) * t, hy + (my - hy) * t
        leg = 700 - (y + depth)
        timber(ic, (x - 8, y + depth - 4), (x - 30, y + depth + leg), 16, "#8e6640", "#4e3522")
        timber(ic, (x + 10, y + depth - 4), (x + 32, y + depth + leg + 4), 16, "#8e6640", "#4e3522")
        if leg > 70:
            timber(ic, (x - 26, y + depth + leg * 0.55), (x + 28, y + depth + leg * 0.55 + 4), 10, "#8e6640", "#4e3522")
    # far board (inside, dark), then the water surface
    ic.fill(ic.poly_mask([(hx + 8, hy - far), (mx + 12, my - far), (mx, my), (hx, hy)]), "#3e2c1a", "#2a1c10",
            noise=0.2)
    water = [(hx + 8, hy - far + 10), (mx + 12, my - far + 10), (mx, my + 2), (hx, hy + 2)]
    wm = ic.poly_mask(water)
    ic.fill(wm, "#bfe4ec", "#5aa0b4", (hy - far, my), noise=0.06)
    lay, d = layer()
    for k in range(1, 7):
        t = k / 7
        x, y = hx + (mx - hx) * t, hy + (my - hy) * t
        d.line([(x + 8, y - far + 10), (x, y + 2)], fill=(52, 34, 18, 230), width=6)
        d.line([(x + 18, y - far + 12), (x + 10, y + 3)], fill=(255, 255, 255, 220), width=5)
    for k in range(10):
        t = ic.random.uniform(0.05, 0.95)
        x, y = hx + (mx - hx) * t, hy + (my - hy) * t - far * 0.5
        d.line([(x, y), (x + 26, y + 26 * (my - hy) / (mx - hx))], fill=(255, 255, 255, 150), width=3)
    composite(ic, lay, wm)
    # near side board: dark planks
    board = [(hx, hy), (mx, my), (mx, my + depth), (hx, hy + depth)]
    ic.fill(ic.poly_mask(board), "#6e4c2c", "#3a2614", (hy, my + depth), noise=0.2)
    ic.line([(hx, hy + depth * 0.5), (mx, my + depth * 0.5)], 3, (30, 18, 8, 170))
    ic.line([(hx, hy + 3), (mx, my + 3)], 4, (255, 228, 186, 120))
    ic.shade(ic.poly_mask([(hx, hy + depth * 0.55), (mx, my + depth * 0.55), (mx, my + depth), (hx, hy + depth)]),
             alpha=0.3)
    for t in (0.3, 0.7):  # batten straps
        x, y = hx + (mx - hx) * t, hy + (my - hy) * t
        ic.line([(x, y), (x, y + depth)], 7, (42, 28, 16))
    ic.outline(board, 5)
    ic.outline([(hx, hy), (hx + 8, hy - far), (mx + 12, my - far), (mx, my)], 5)
    # head box at the top end, water brimming in it
    bx0, bx1, by0, by1 = hx - 84, hx + 10, hy - 56, hy + depth + 8
    ic.rect((bx0, by0 + 16, bx1, by1), "#8a6440", "#4a3220", noise=0.2)
    ic.shade(ic.mask("rectangle", (bx1 - 26, by0 + 16, bx1, by1)), (20, 10, 4), 0.35)
    ic.line([(bx0, by0 + 40), (bx1, by0 + 40)], 3, (30, 18, 8, 160))
    ic.poly([(bx0, by0 + 16), (bx1, by0 + 16), (bx1 + 10, by0), (bx0 + 10, by0)], "#bfe4ec", "#6aaabb", edge=5,
            noise=0.06)
    ic.line([(bx0 + 20, by0 + 8), (bx1 - 10, by0 + 8)], 3, (255, 255, 255, 200))
    return mx + 6, my + 10


def gold_pan(ic: Icon, cx: float, cy: float, rx: float, ry: float) -> None:
    """Iron pan tilted towards the viewer: lit rim, dark wet sand, a few bright flakes, one gleam (new)."""
    ic.shade(ic.mask("ellipse", (cx - rx + 8, cy - ry + 18, cx + rx + 18, cy + ry + 22)), (30, 20, 10), 0.5, blur=6,
             clip=False)
    ic.fill(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), "#8a8480", "#2e2a28",
            radial=(cx - rx * 0.6, cy - ry * 0.8, rx * 2.1), noise=0.12)
    inner = (cx - rx * 0.8, cy - ry * 0.76, cx + rx * 0.8, cy + ry * 0.8)
    ic.fill(ic.mask("ellipse", inner), "#2e2a26", "#4a443c", radial=(cx - rx * 0.2, cy - ry * 0.4, rx), noise=0.2)
    ic.shade(ic.mask("ellipse", (inner[0], inner[1], inner[2], cy - ry * 0.2)), alpha=0.35, blur=5)
    ic.overlay(lambda d: d.arc((cx - rx + 3, cy - ry + 3, cx + rx - 3, cy + ry - 3), 150, 300,
                               fill=(236, 228, 214, 220), width=6))
    ic.overlay(lambda d: d.arc((cx - rx + 3, cy - ry + 3, cx + rx - 3, cy + ry - 3), 330, 110,
                               fill=(18, 14, 12, 200), width=6))
    # a few bright flakes gathered at the low front of the pan
    lay, d = layer()
    for fx, fy, s in ((-0.1, 0.42, 13), (0.14, 0.5, 11), (0.3, 0.36, 9), (-0.3, 0.3, 8), (0.04, 0.26, 7)):
        x, y = cx + fx * rx, cy + fy * ry
        d.ellipse((x - s, y - s * 0.7, x + s, y + s * 0.7), fill=(255, 204, 60, 255))
        d.ellipse((x - s * 0.5, y - s * 0.55, x + s * 0.2, y - s * 0.05), fill=(255, 248, 210, 230))
    composite(ic, lay, ic.mask("ellipse", inner))
    ic.overlay(lambda d: d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=(30, 24, 20, 230), width=5))
    glints(ic, [(cx - rx * 0.1, cy + ry * 0.38)], 9, (255, 252, 230))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95
    X0, X1 = 100, 960

    band = ic.water_band(top=790, bottom=866, x0=X0, x1=X1, inset=36, sag=22, light=W_LIGHT, deep=W_DEEP)

    # ---- dark back bank behind the windlass: the higher ground the shaft is sunk from
    back = [(300, 700), (306, 520), (340, 450), (400, 420), (470, 430), (540, 416), (610, 470), (660, 560),
            (680, 700)]
    bm = ic.poly_mask(back)
    ic.fill(bm, "#4e3822", "#22160a", (420, 700), noise=0.3, chroma=0.1)
    with ic.clipped(bm):
        pebbles(ic, bm, (300, 420, 680, 700), 36, 4, 10)
        ic.shade(bm, (12, 8, 2), 0.4)
        ic.shade(ic.mask("rectangle", (0, 410, 1024, 450)), (255, 230, 180), 0.16, blur=10)
    ic.outline(back)
    for gx, gy, gw in ((400, 424, 36), (590, 450, 40)):
        weeds(ic, gx, gy, gw)

    # ---- spoil heap: a distinct pale cone at the left with its own contact shadow
    ic.shade(ic.mask("ellipse", (X0 + 10, 664, 350, 724)), (30, 20, 10), 0.6, blur=10, clip=False)
    spoil = [(X0, 700), (X0 + 14, 640), (132, 560), (160, 470), (184, 386), (206, 346), (226, 334), (248, 344),
             (270, 386), (296, 480), (318, 580), (336, 700)]
    sm = ic.poly_mask(spoil)
    ic.fill(sm, "#ead6a0", "#a88a54", radial=(170, 340, 380), noise=0.22, chroma=0.1)
    with ic.clipped(sm):
        ic.shade(ic.poly_mask([(236, 336), (248, 344), (270, 386), (296, 480), (318, 580), (336, 700), (236, 700),
                               (226, 480)]), (50, 30, 12), 0.38, blur=14)
        pebbles(ic, sm, (X0 + 10, 320, 376, 700), 54, 5, 12)
        ic.shade(ic.mask("rectangle", (0, 660, 1024, 720)), (40, 24, 10), 0.3, blur=12)
    ic.outline(spoil)

    # ---- bank: top surface and a near-vertical cut face of gravel and cobbles down to the water
    top = [(X0, 700), (X0 + 20, 680), (X1 - 40, 690), (X1 - 14, 716), (X0, 724)]
    ic.poly(top, "#b8965e", "#8a6a3e", noise=0.25, edge=0)
    face = [(X0, 722), (X1 - 10, 714), (X1, 800), (X0 + 6, 808)]
    fm = ic.poly_mask(face)
    ic.fill(fm, "#6e5032", "#3a2816", (714, 808), noise=0.3, chroma=0.1)
    with ic.clipped(fm):
        pebbles(ic, fm, (X0, 730, X1, 810), 90, 6, 14)
        for _ in range(9):  # cobbles in the face
            x, y = ic.random.uniform(X0 + 30, X1 - 30), ic.random.uniform(740, 790)
            ic.chunk(x, y, ic.random.uniform(14, 22), "#a09078", "#4e4436", glint=(255, 240, 210))
        ic.shade(ic.mask("rectangle", (0, 714, 1024, 746)), (10, 6, 2), 0.55, blur=8)  # cast shadow under the lip
        ic.shade(ic.mask("rectangle", (0, 780, 1024, 820)), (20, 30, 34), 0.3, blur=10)
    ic.outline(face)
    ic.line([(X0, 722), (X1 - 10, 714)], 6, (255, 236, 196, 110))

    # ---- pit and windlass: the hero, lit against the dark back bank
    ic.fill(ic.mask("ellipse", (350, 668, 576, 718)), "#5a4028", "#3a2818", noise=0.3)
    ic.fill(ic.mask("ellipse", (370, 676, 556, 712)), "#120c06", "#060402", noise=0.1)
    windlass(ic, 372, 548, 308, 706, 700)
    # shovel stuck in the spoil
    ic.line([(128, 650), (156, 500)], 14, DARK)
    ic.line([(128, 650), (156, 500)], 8, (150, 110, 70))
    ic.poly([(110, 638), (146, 646), (138, 702), (104, 692)], "#7a7674", "#3a3634", edge=4)

    # ---- sluice from its head box down to the stream
    mouth = sluice(ic, (720, 450), (880, 624))
    spout(ic, mouth[0], mouth[1] - 4, 30, 172, 24)

    # ---- stream foam, the gold pan propped against the bank, weeds
    ic.foam(X0 + 60, X1 - 60, 806)
    weeds(ic, X0 + 20, 724, 36)
    gold_pan(ic, 640, 768, 84, 58)
