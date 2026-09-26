"""Gold Stamp Mill (gold_stamp_mill): a water-driven battery of stamps crushing gold quartz.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/gold_stamp_mill/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/gold_stamp_mill

Identity: the stamps. An open-fronted timber mill house under a tall roof, its near-black interior
behind three thick pale stamp stems with heavy iron shoes: the left one lifted high by a wedge cam
under its tappet, the middle one down in the mortar box, the right one half way. A thick camshaft runs
from the hub of a smaller undershot wheel, half hidden behind its race wall. A heap of white gold
quartz with bright flecks in front, and a sloping copper amalgamation table on the quay whose grey
slurry runs off into the tailrace. Tier 1 of gold_diggings: same gravel, water, timber and gold palette.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 61
REFS = ("sawmill", "lumber_mill", "schwaz_mine", "iron_mill")

W_LIGHT, W_DEEP = "#7cb6c6", "#2a5c6e"
WOOD, WOOD_DK = "#8e6640", "#4e3522"
STEM, STEM_DK = "#d2b286", "#8a6a44"
IRON, IRON_DK = "#5a5856", "#262422"
DARK = (28, 18, 12)

BAND_TOP, BAND_BOT = 772, 868
QUAY_TOP, QUAY_FACE, QUAY_BASE = 772, 796, 850


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


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form, no outlines (from cookshop)."""
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
    """Roof plane of overlapping shingles with per-shingle tone and course shadows (from cookshop)."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow = Image.new("L", (SIZE, SIZE), 0)
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
        td.line([(0, yl - 4), (SIZE, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (SIZE, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    composite(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap per board (from tavern)."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay, d = layer()
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
    composite(ic, lay, m)


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


def post(ic: Icon, x: float, y0: float, y1: float, w: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Upright squared timber lit on its left face, shaded on its right (new)."""
    ic.fill(ic.mask("rectangle", (x - w / 2, y0, x + w / 2, y1)), c1, c2, (x - w / 2, x + w / 2), vertical=False,
            noise=0.18)
    ic.line([(x - w / 2 + 5, y0 + 4), (x - w / 2 + 5, y1 - 4)], 4, (255, 232, 196, 90))
    ic.outline([(x - w / 2, y0), (x + w / 2, y0), (x + w / 2, y1), (x - w / 2, y1)], 4, (40, 26, 16, 190))


def spout(ic: Icon, x: float, y: float, dx: float, dy: float, w: float = 16, col=(236, 246, 247)) -> None:
    """Water jet leaving an opening at (x, y), arcing by (dx, dy), with a splash (from canal_lock_works)."""
    ts = np.linspace(0, 1, 18)
    path = [(x + dx * t, y + dy * t * t) for t in ts]
    lay, d = layer()
    d.line(path, fill=(170, 200, 205, 230), width=int(w + 8), joint="curve")
    d.line(path, fill=col + (240,), width=int(w), joint="curve")
    ex, ey = path[-1]
    for _ in range(12):
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


# ---------------------------------------------------------------- parts
def water_wheel(ic: Icon, cx: float, cy: float, r: float, n: int = 14) -> Image.Image:
    """Undershot wheel seen side-on, shaped by tone rather than outlines: paddles, rim, spokes, hub.
    Returns its mask."""
    rim_w = 34
    wheel = ic.mask("ellipse", (cx - r - 40, cy - r - 40, cx + r + 40, cy + r + 40))
    far = ImageChops.subtract(ic.mask("ellipse", (cx - r + 20, cy - r - 12, cx + r + 20, cy + r - 12)),
                              ic.mask("ellipse", (cx - r + 20 + rim_w, cy - r - 12 + rim_w, cx + r + 20 - rim_w,
                                                  cy + r - 12 - rim_w)))
    ic.fill(far, "#4e3824", "#2a1c10", noise=0.2)
    for k in range(n):
        a = 2 * math.pi * k / n + 0.1
        ca, sa = math.cos(a), math.sin(a)
        tx, ty = -sa, ca
        p = [(cx + ca * (r - 16) + tx * 14, cy + sa * (r - 16) + ty * 14),
             (cx + ca * (r + 12) + tx * 15, cy + sa * (r + 12) + ty * 15),
             (cx + ca * (r + 12) - tx * 15, cy + sa * (r + 12) - ty * 15),
             (cx + ca * (r - 16) - tx * 14, cy + sa * (r - 16) - ty * 14)]
        ic.poly(p, "#8e6a46", "#4e3522", edge=0)
        ic.shade(ic.poly_mask(p[2:] + [((p[1][0] + p[2][0]) / 2, (p[1][1] + p[2][1]) / 2)]), alpha=0.3)
        if sa > 0.1:
            ic.shade(ic.poly_mask(p), alpha=0.25)
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r + rim_w, cy - r + rim_w, cx + r - rim_w, cy + r - rim_w)))
    ic.fill(ring, "#9a7048", "#4a3220", radial=(cx - r * 0.7, cy - r * 0.7, r * 2.2), noise=0.2)
    ic.overlay(lambda dd: dd.arc((cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), 160, 260,
                                 fill=(255, 228, 186, 110), width=6))
    for k in range(6):
        a = math.pi * k / 3 + 0.3
        p1 = (cx + math.cos(a) * (r - rim_w + 4), cy + math.sin(a) * (r - rim_w + 4))
        ic.line([(cx, cy), p1], 24, (110, 80, 52))
        ic.line([(cx - 4, cy - 4), (p1[0] - 4, p1[1] - 4)], 5, (255, 228, 186, 70))
    ic.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), "#8a6440", "#4a3420", edge=0)
    ic.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), IRON, IRON_DK, edge=0)
    ic.shade(ic.intersect(wheel, ic.mask("ellipse", (cx - r * 0.2, cy - r * 0.1, cx + r * 1.6, cy + r * 1.5))),
             alpha=0.25, blur=30)
    return wheel


def stamp(ic: Icon, x: float, top: float, shoe: float, w: float = 48) -> tuple[float, float]:
    """One stamp: a thick pale lit stem, a tappet collar, a heavy dark iron head and shoe whose
    bottom is at ``shoe``. Returns the collar's underside (x, y)."""
    sw = w
    ic.fill(ic.mask("rectangle", (x - sw / 2, top, x + sw / 2, shoe - 96)), "#f2dcae", "#a8804e",
            (x - sw / 2, x + sw / 2), vertical=False, noise=0.14)
    ic.shade(ic.mask("rectangle", (x + sw * 0.18, top, x + sw / 2, shoe - 96)), (30, 16, 6), 0.35)
    ic.line([(x - sw / 2 + 6, top + 4), (x - sw / 2 + 6, shoe - 100)], 5, (255, 246, 220, 150))
    ic.outline([(x - sw / 2, top), (x + sw / 2, top), (x + sw / 2, shoe - 96), (x - sw / 2, shoe - 96)], 4,
               (40, 26, 16, 200))
    # heavy iron head and shoe
    hw = sw * 0.72
    ic.fill(ic.mask("rectangle", (x - hw, shoe - 100, x + hw, shoe)), "#6a6662", "#1e1c1a",
            (x - hw, x + hw), vertical=False, noise=0.12)
    ic.line([(x - hw + 6, shoe - 96), (x - hw + 6, shoe - 6)], 5, (210, 210, 204, 130))
    ic.line([(x - hw, shoe - 64), (x + hw, shoe - 64)], 7, (16, 14, 12, 230))
    ic.outline([(x - hw, shoe - 100), (x + hw, shoe - 100), (x + hw, shoe), (x - hw, shoe)], 5, (12, 10, 8, 240))
    # tappet collar
    cy = shoe - 172
    ic.fill(ic.mask("rectangle", (x - sw * 0.8, cy - 30, x + sw * 0.8, cy)), "#8a8480", "#2e2c2a",
            (x - sw, x + sw), vertical=False, noise=0.1)
    ic.line([(x - sw * 0.8 + 4, cy - 26), (x + sw * 0.8 - 4, cy - 26)], 4, (230, 226, 216, 140))
    ic.outline([(x - sw * 0.8, cy - 30), (x + sw * 0.8, cy - 30), (x + sw * 0.8, cy), (x - sw * 0.8, cy)], 4,
               (12, 10, 8, 230))
    return x - sw * 0.8, cy


def cam(ic: Icon, sx: float, sy: float, tip: tuple[float, float], w: float = 44) -> None:
    """Wedge-shaped cam on the shaft at (sx, sy), its nose at ``tip`` (new)."""
    tx, ty = tip
    pts = [(sx - w * 0.6, sy + 10), (sx + w * 0.6, sy + 10), (tx + 12, ty + 4), (tx - 14, ty)]
    ic.poly(pts, "#a47a4e", "#4a3220", noise=0.16, edge=0)
    ic.shade(ic.poly_mask([(sx + w * 0.1, sy + 10), (sx + w * 0.6, sy + 10), (tx + 12, ty + 4), (tx, ty + 2)]),
             (20, 10, 4), 0.35)
    ic.outline(pts, 4, (30, 18, 8, 220))
    ic.line([(tx - 14, ty), (tx + 12, ty + 4)], 6, IRON_DK)


def copper_table(ic: Icon, x0: float, y0: float, x1: float, y1: float, legs_to: float) -> tuple[float, float]:
    """Sloping amalgamation table: a timber frame with a copper plate falling to the right, warm metallic
    sheen, a thin grey slurry film over it. Returns the low lip (x, y)."""
    th = 22
    for lx, ly in ((x0 + 20, y0 + th), (x1 - 24, y1 + th)):
        post(ic, lx, ly, legs_to, 20)
    ic.poly([(x0, y0), (x1, y1), (x1, y1 + th), (x0, y0 + th)], "#7a5434", "#4a3220", edge=4)
    plate = [(x0 + 6, y0 - 30), (x1 - 6, y1 - 30), (x1, y1), (x0, y0)]
    pm = ic.poly_mask(plate)
    ic.fill(pm, "#ffb468", "#a04a18", (x0, x1), vertical=False, noise=0.1, chroma=0.04)
    lay, d = layer()
    d.line([(x0 + 24, y0 - 22), (x1 - 30, y1 - 22)], fill=(255, 244, 214, 220), width=7)
    d.line([(x0 + 60, y0 - 12), (x1 - 20, y1 - 12)], fill=(255, 214, 160, 90), width=5)
    for k in range(4):  # grey slurry film trickling down the plate
        f = 0.15 + 0.22 * k
        d.line([(x0 + 16 + (x1 - x0) * f * 0.2, y0 - 24 + 22 * f), (x1 - 10, y1 - 24 + 22 * f)],
               fill=(150, 146, 136, 150), width=5)
    composite(ic, lay, pm)
    ic.outline(plate, 4, (40, 22, 10, 220))
    return x1 - 4, y1 - 8


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95

    band = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=40, x1=990, inset=34, sag=26, light=W_LIGHT, deep=W_DEEP)

    # ---- wheel (smaller, partly hidden behind the race wall), driving the camshaft
    WX, WY, WR = 210, 606, 150
    wm = water_wheel(ic, WX, WY, WR)

    # ---- mill house: near-black interior behind the stamps
    hx0, hx1, eave, ridge = 420, 820, 314, 132
    planks(ic, (hx0 + 20, eave, hx1 - 20, QUAY_TOP), "#3a2c1e", "#140e08", board=34)
    ic.shade(ic.mask("rectangle", (hx0 + 20, eave, hx1 - 20, QUAY_TOP)), alpha=0.45, blur=20)

    # camshaft: a thick shaft from the wheel hub into the house
    CY = 600
    ic.fill(ic.mask("rectangle", (WX, CY - 30, hx1 - 30, CY + 30)), "#a07648", "#4a3420", noise=0.16)
    ic.line([(WX, CY - 18), (hx1 - 30, CY - 18)], 5, (255, 228, 186, 110))
    ic.shade(ic.mask("rectangle", (WX, CY + 8, hx1 - 30, CY + 30)), (20, 10, 4), 0.35)
    ic.outline([(WX, CY - 30), (hx1 - 30, CY - 30), (hx1 - 30, CY + 30), (WX, CY + 30)], 5, (30, 18, 8, 220))
    for x in (hx0 + 40, hx1 - 60):
        ic.line([(x, CY - 30), (x, CY + 30)], 10, IRON_DK)
    ic.ellipse((WX - 22, CY - 22, WX + 22, CY + 22), IRON, IRON_DK, edge=4)

    # stamps: left raised high on its cam, middle down in the mortar, right half way
    xs, lifts = (520, 620, 720), (130, 0, 60)
    collars = [stamp(ic, x, 200, 750 - lift) for x, lift in zip(xs, lifts)]
    # guide beams the stems slide through
    for y in (356,):
        timber(ic, (hx0 + 10, y), (hx1 - 10, y), 30, "#9a7048", "#4e3522")
        for x in xs:
            ic.shade(ic.mask("rectangle", (x - 24, y + 15, x + 24, y + 34)), alpha=0.4, blur=4)
    # cams: the raised stamp's cam wedge pushes up under its collar, the others turned away
    (cx0, cy0), (cx1, cy1), (cx2, cy2) = collars
    cam(ic, cx0 - 4, CY - 26, (cx0 + 16, cy0 + 2), 56)
    cam(ic, cx1 - 6, CY + 24, (cx1 - 40, CY + 74), 50)
    cam(ic, cx2 - 4, CY - 26, (cx2 + 16, cy2 + 2), 56)
    # mortar box the shoes drop into, crushed quartz in its mouth
    ic.poly([(456, 712), (788, 712), (792, QUAY_TOP + 4), (452, QUAY_TOP + 4)], "#6e4e32", "#34220f", noise=0.2)
    ic.fill(ic.mask("rectangle", (452, 700, 792, 718)), "#c0986a", "#7a5836", noise=0.2)
    ic.outline([(452, 700), (792, 700), (792, 718), (452, 718)], 4, (30, 18, 8, 220))
    for x in (470, 570, 670, 772):
        ic.line([(x, 718), (x, QUAY_TOP)], 10, IRON_DK)
        ic.line([(x - 3, 718), (x - 3, QUAY_TOP)], 3, (170, 166, 160, 120))
    ic.shade(ic.mask("rectangle", (452, 718, 792, 734)), alpha=0.45, blur=5)
    for x in (474, 566, 674, 770):
        ic.chunk(x, 700, 12, "#f2ece0", "#a09888", glint=(255, 255, 255))
    # posts and a tall roof over the stamp frame
    post(ic, hx0 + 18, 330, QUAY_TOP, 46)
    post(ic, hx1 - 18, 330, QUAY_TOP, 46)
    shingles(ic, [(hx0 - 40, eave + 10), (hx1 + 40, eave + 10), (hx1 - 40, ridge), (hx0 + 40, ridge)], "#9a7a58",
             "#5a4230", course=30, stagger=36)
    ic.line([(hx0 + 40, ridge + 2), (hx1 - 40, ridge + 2)], 14, (70, 50, 32))
    ic.shade(ic.mask("rectangle", (hx0 + 20, eave + 10, hx1 - 20, eave + 70)), alpha=0.55, blur=14)

    # ---- stone quay the mill stands on
    stones(ic, (400, QUAY_TOP, 990, QUAY_BASE + 20), "#a89c88", "#6a6052", course=30)
    ic.fill(ic.mask("rectangle", (400, QUAY_TOP, 990, QUAY_FACE)), "#c0b29a", "#8a7e6a", noise=0.18)
    ic.outline([(400, QUAY_TOP), (990, QUAY_TOP), (990, QUAY_BASE + 20), (400, QUAY_BASE + 20)], 5)
    ic.shade(ic.mask("rectangle", (400, QUAY_FACE, 990, QUAY_FACE + 18)), alpha=0.4, blur=6)

    # ---- copper amalgamation table on the quay at the right, slurry off its low end into the tailrace
    lip = copper_table(ic, 814, 640, 982, 692, QUAY_TOP)
    spout(ic, lip[0], lip[1], 14, 120, 10, col=(170, 166, 156))

    # ---- stone race wall in front of the lower wheel
    stones(ic, (40, 690, 420, BAND_TOP + 30), "#9a8e7a", "#5a5044", course=30)
    ic.fill(ic.mask("rectangle", (34, 676, 426, 700)), "#c0b29a", "#8a7e6a", noise=0.18)
    ic.outline([(34, 676), (426, 676), (426, BAND_TOP + 30), (40, BAND_TOP + 30), (40, 700), (34, 700)], 5)
    ic.shade(ic.mask("rectangle", (40, 700, 420, 722)), alpha=0.4, blur=6)
    quay = ic.mask("rectangle", (400, QUAY_TOP, 990, QUAY_BASE + 40))
    ic.waterline(quay, QUAY_BASE)
    ic.waterline(ic.mask("rectangle", (40, 690, 420, BAND_TOP + 60)), BAND_TOP + 36)
    ic.foam(60, 430, BAND_TOP + 36)
    ic.foam(400, 980, QUAY_BASE)

    # ---- heap of white-to-cream gold quartz between wheel and house, gold flecks
    ic.heap(300, 480, QUAY_BASE - 20, 650, 24, 6, body=("#b8ae9c", "#5a5244"), lump=("#f6f0e2", "#b0a48c"),
            odd=("#e8d8b0", "#9a8a68"), odd_share=0.3)
    lay, d = layer()
    for x, y, s in ((352, 700, 7), (396, 736, 8), (436, 772, 6), (330, 790, 7), (418, 812, 6), (372, 766, 5)):
        d.ellipse((x - s, y - s * 0.7, x + s, y + s * 0.7), fill=(255, 206, 60, 255))
    composite(ic, lay)
    glints(ic, [(396, 736), (352, 700), (418, 812)], 7)
    # a shovel against the heap
    ic.line([(290, 836), (330, 680)], 14, DARK)
    ic.line([(290, 836), (330, 680)], 8, (150, 110, 70))
