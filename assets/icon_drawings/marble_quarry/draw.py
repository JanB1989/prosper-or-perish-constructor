"""Marble Quarry (marble_quarry): white veined marble benches cut in steps into a weathered hill.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/marble_quarry/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/marble_quarry

Composition: a hillside rising high on the left and falling away to the right, with a broken rocky
crest and scrub only along it. Three staggered benches are cut into it: recessed white faces with a
dark shadowed side wall on the left, a lit rough return on the right, a cast shadow under every lip,
rows of half drill holes, chipped corners and warm iron staining; rough marble and earth show on
both sides so the white narrows upward. On the middle bench a half-cut block stands proud, split
along its top with three iron wedges. On the quarry floor a loose block lies turned on a skid, roped,
its rough sawn end in shadow; a crowbar, a drill bar with sledge and a heap of marble chips. Vanilla
stone_quarry is a treadwheel crane over grey blocks; this one reads through the white stepped cut.
First tier of the marble chain (the Marble Saw Yard adds the sawing shed and water wheel).
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 11
REFS = ("stone_quarry", "clay_pit", "sand_pit", "schwaz_mine")

MARBLE = "#e6ddcc"        # lit marble, faintly warm
MARBLE_MID = "#bfb19a"
MARBLE_DK = "#8a7d6a"
TOP = "#efe7d6"           # bench tops catch the light
ROCK = "#a8845a"          # weathered, iron-stained hill
ROCK_DK = "#4a3522"
VEIN = (92, 96, 106)
WOOD, WOOD_DK = "#8a6240", "#4c3422"
IRON = (52, 50, 52)


# ---- helpers ---------------------------------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def veins(ic: Icon, mask: Image.Image, box, n: int, direction: float = 30, color=VEIN, strength: float = 1.0) -> None:
    """Marble veining: wandering grey threads with a soft cloudy halo and the odd branch, clipped to ``mask``."""
    x0, y0, x1, y1 = box
    R = ic.random
    lay, d = layer()
    soft, ds = layer()
    for _ in range(n):
        x, y = R.uniform(x0 - 60, x1), R.uniform(y0 - 20, y1)
        ang = math.radians(direction + R.uniform(-30, 30))
        pts = [(x, y)]
        for _ in range(int(R.uniform(70, 280) / 12)):
            ang += R.uniform(-0.45, 0.45)
            x, y = x + math.cos(ang) * 12, y + math.sin(ang) * 12
            pts.append((x, y))
        w = R.choice((3, 3, 4, 5, 7))
        ds.line(pts, fill=color + (int(60 * strength),), width=w * 5, joint="curve")
        d.line(pts, fill=color + (int(R.randint(120, 190) * strength),), width=w, joint="curve")
        if R.random() < 0.5 and len(pts) > 6:  # branch
            bx, by = pts[len(pts) // 2]
            ba = ang + R.choice((-1, 1)) * R.uniform(0.6, 1.1)
            bp = [(bx, by)]
            for _ in range(R.randint(3, 8)):
                ba += R.uniform(-0.4, 0.4)
                bx, by = bx + math.cos(ba) * 11, by + math.sin(ba) * 11
                bp.append((bx, by))
            d.line(bp, fill=color + (int(110 * strength),), width=max(2, w - 2), joint="curve")
    composite(ic, soft.filter(ImageFilter.GaussianBlur(7)), mask)
    composite(ic, lay.filter(ImageFilter.GaussianBlur(0.8)), mask)


def chunk(ic: Icon, cx: float, cy: float, r: float, base=MARBLE, dark=MARBLE_DK) -> None:
    pts = ic.jitter(cx, cy, r, r * 0.72, ic.random.randint(6, 8), 0.18)
    ic.fill(ic.poly_mask(pts), base, dark, radial=(cx - r, cy - r, r * 2.4), noise=0.18)
    top = [(cx - r * 0.7, cy - r * 0.05), (cx - r * 0.2, cy - r * 0.6), (cx + r * 0.4, cy - r * 0.45), (cx, cy)]
    ic.shade(ic.poly_mask(top), (255, 252, 244), 0.35)
    ic.shade(ic.poly_mask([(cx, cy), (cx + r * 0.9, cy - r * 0.1), (cx + r * 0.6, cy + r * 0.7), (cx - r * 0.3, cy + r * 0.7)]),
             (30, 28, 26), 0.3)
    ic.outline(pts, 4, (60, 54, 48, 190))


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    ic.fill(ic.poly_mask(pts), c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def scrub(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Low maquis bush on the hill crown."""
    R = ic.random
    m = Image.new("L", (SIZE, SIZE), 0)
    for _ in range(6):
        bx, by = cx + R.uniform(-r * 0.6, r * 0.6), cy + R.uniform(-r * 0.25, r * 0.2)
        m = ImageChops.lighter(m, ic.poly_mask(ic.jitter(bx, by, r * 0.5, r * 0.38, 10, 0.12)))
    ic.fill(m, "#7d8a4a", "#34401e", radial=(cx - r * 0.6, cy - r * 0.5, r * 1.8), noise=0.3)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (cx - r * 0.2, cy, cx + r * 1.4, cy + r))), (10, 16, 6), 0.35, blur=6)



RUST = (168, 94, 38)


def drill_grooves(ic: Icon, mask: Image.Image, x0: float, x1: float, y0: float, y1: float, step: float = 24) -> None:
    """Rows of half drill holes left on a split face: parallel short vertical grooves, dark core with a
    lit right lip, breaking off at uneven depths."""
    R = ic.random
    lay, d = layer()
    x = x0
    while x < x1:
        top = y0 + R.uniform(0, 10)
        bot = top + R.uniform(0.45, 0.95) * (y1 - top)
        d.line([(x, top), (x + R.uniform(-2, 2), bot)], fill=(58, 52, 48, 150), width=6)
        d.line([(x + 5, top + 2), (x + 5, bot)], fill=(255, 252, 244, 110), width=3)
        x += step * R.uniform(0.85, 1.15)
    composite(ic, lay.filter(ImageFilter.GaussianBlur(0.6)), mask)


def rust(ic: Icon, mask: Image.Image, x0: float, x1: float, y0: float, y1: float, n: int, strength: float = 1.0) -> None:
    """Iron staining washed down a face: warm orange-brown streaks tapering downwards plus blotches."""
    R = ic.random
    for _ in range(n):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.35, 1.0) * (y1 - y0)
        w = R.uniform(8, 20)
        streak = [(sx - w, y0 - 4), (sx + w, y0 - 4), (sx + R.uniform(-4, 6) + 3, y0 + ln), (sx - 3, y0 + ln)]
        ic.shade(ic.intersect(mask, ic.poly_mask(streak)), RUST, R.uniform(0.3, 0.5) * strength, blur=5)
    for _ in range(n // 2):
        bx, by = R.uniform(x0, x1), R.uniform(y0, y0 + (y1 - y0) * 0.4)
        ic.shade(ic.intersect(mask, ic.poly_mask(ic.jitter(bx, by, R.uniform(10, 24), R.uniform(6, 14), 8, 0.3))),
                 (140, 78, 34), 0.35 * strength, blur=6)


def rough(ic: Icon, pts, c1, c2, vertical: bool = True, cracks: int = 3) -> Image.Image:
    """Unworked rock or rough marble surface: noisy fill, blotches, a few cracks."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    span = (min(ys), max(ys)) if vertical else (min(xs), max(xs))
    ic.fill(m, c1, c2, span, vertical, noise=0.3, chroma=0.08)
    R = ic.random
    for _ in range(int((max(xs) - min(xs)) * (max(ys) - min(ys)) / 2500) + 1):
        bx, by = R.uniform(min(xs), max(xs)), R.uniform(min(ys), max(ys))
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(bx, by, R.uniform(8, 22), R.uniform(6, 14), 7, 0.3))),
                 (255, 244, 220) if R.random() < 0.4 else (20, 16, 12), 0.18, blur=3)
    lay, d = layer()
    for _ in range(cracks):
        x, y = R.uniform(min(xs), max(xs)), R.uniform(min(ys), max(ys))
        p = [(x, y)]
        for _ in range(4):
            x, y = x + R.uniform(-14, 14), y + R.uniform(10, 26)
            p.append((x, y))
        d.line(p, fill=(40, 30, 22, 150), width=4, joint="curve")
    composite(ic, lay, m)
    return m


def level(ic: Icon, a: float, b: float, face: float, foot: float, al: float, bl: float, td: float,
          grooves=(), chips=(True, True)) -> Image.Image:
    """One bench cut into the hill, seen from the front: the white back wall (riser) recessed between a
    dark left side wall and a lit rough right return, the lit tread at its foot widening towards the viewer,
    a cast shadow under the lip above. Returns the riser mask."""
    R = ic.random
    # side walls of the cut
    lw = [(al, face - 22), (a, face), (a, foot), (al, foot + td)]
    rough(ic, lw, "#6a5a48", "#3c3228", cracks=2)
    ic.shade(ic.poly_mask(lw), (18, 14, 12), 0.25)
    rw = [(b, face), (bl, face - 18), (bl, foot + td), (b, foot)]
    rough(ic, rw, "#bc9e74", "#7a5c3e", cracks=2)
    ic.shade(ic.poly_mask([(b, face), (bl, face - 18), (bl, face + 40), (b, face + 50)]), (30, 22, 14), 0.3, blur=8)
    # the riser: recessed white face with slightly wandering edges
    j = lambda: R.uniform(-6, 6)  # noqa: E731
    rp = [(a, face), (b, face), (b + j(), (face + foot) / 2), (b, foot), (a, foot), (a + j(), (face + foot) / 2)]
    rm = ic.poly_mask(rp)
    ic.fill(rm, MARBLE, MARBLE_MID, (a - 80, b + 220), vertical=False, noise=0.13, chroma=0.03)
    veins(ic, rm, (a, face, b, foot), int((b - a) / 60) + 1)
    for gx0, gx1 in grooves:
        drill_grooves(ic, rm, gx0, gx1, face + 10, foot)
    rust(ic, rm, a + 10, b - 10, face, foot, int((b - a) / 45))
    # grime at the foot, cool shade to the right, cast shadows from the lip and the left wall
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (0, foot - 40, SIZE, foot + 10))), (70, 60, 50), 0.35, blur=14)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (a + (b - a) * 0.6, face, SIZE, foot))), (52, 56, 72), 0.22, blur=40)
    lip = [(a - 10, face - 4), (b + 10, face - 4), (b + 10, face + 22)]
    for k in range(8):
        lip.append((b - (b - a) * (k + 1) / 8, face + R.uniform(18, 34)))
    ic.shade(ic.intersect(rm, ic.poly_mask(lip)), (30, 26, 24), 0.6, blur=7)
    ic.shade(ic.intersect(rm, ic.poly_mask([(a, face), (a + 70, face), (a + 30, foot), (a, foot)])), (24, 20, 18), 0.35,
             blur=10)
    # chipped corners: broken-away bits showing rough grey marble in shade
    if chips[0]:
        cp = [(a, face), (a + R.uniform(26, 40), face), (a + 14, face + R.uniform(24, 40)), (a, face + R.uniform(30, 44))]
        ic.fill(ic.poly_mask(cp), "#8e8272", "#5e5448", noise=0.25)
        ic.outline(cp, 3, (50, 44, 38, 170))
    if chips[1]:
        cp = [(b, face), (b - R.uniform(30, 46), face), (b - 20, face + R.uniform(16, 30)), (b, face + R.uniform(40, 60))]
        ic.fill(ic.poly_mask(cp), "#a09482", "#6c6254", noise=0.25)
        ic.outline(cp, 3, (50, 44, 38, 170))
    ic.outline(rp, 4, (60, 52, 44, 170))
    # tread at the foot, lit, dusted with chips; shadow of the left wall across its left end
    tp = [(a, foot), (b, foot), (bl, foot + td), (al, foot + td)]
    tm = ic.poly_mask(tp)
    ic.fill(tm, "#cfc0a4", TOP, (foot, foot + td), noise=0.16, chroma=0.03)
    lay, d = layer()
    for _ in range(int((bl - al) / 16)):
        cx, cy = R.uniform(al + 10, bl - 10), R.uniform(foot + 4, foot + td - 4)
        r = R.uniform(3, 7)
        d.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=(120, 110, 96, R.randint(70, 140)))
    composite(ic, lay, tm)
    ic.shade(ic.intersect(tm, ic.poly_mask([(a, foot), (a + 60, foot), (al + 20, foot + td), (al, foot + td)])),
             (24, 20, 18), 0.35, blur=6)
    ic.line([(al + 6, foot + td - 1), (bl - 6, foot + td - 1)], 4, (255, 253, 246, 150))  # worn front arris
    ic.outline(tp, 3, (60, 52, 44, 130))
    return rm


def standing_block(ic: Icon, x0: float, x1: float, y0: float, y1: float, depth: float, shift: float,
                   wedges: int = 0) -> None:
    """A block half cut free, still standing proud on its bench: lit top, veined front, shaded right end.
    With ``wedges`` a split line runs along the top with iron wedges driven into it."""
    tp = [(x0 + shift, y0 - depth), (x1 + shift, y0 - depth), (x1, y0), (x0, y0)]
    ic.fill(ic.poly_mask(tp), TOP, "#d6cab4", (y0 - depth, y0), noise=0.12, chroma=0.03)
    ep = [(x1, y0), (x1 + shift, y0 - depth), (x1 + shift, y1 - depth * 0.6), (x1, y1)]
    rough(ic, ep, "#9a8e7c", "#625848", cracks=1)
    fp = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    fm = ic.poly_mask(fp)
    ic.fill(fm, MARBLE, MARBLE_MID, (x0 - 40, x1 + 120), vertical=False, noise=0.12, chroma=0.03)
    veins(ic, fm, (x0, y0, x1, y1), 2)
    drill_grooves(ic, fm, x0 + 14, x0 + (x1 - x0) * 0.45, y0 + 4, y1, step=22)
    rust(ic, fm, x0 + 8, x1 - 8, y0, y1, 3, 0.8)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, y1 - 24, SIZE, y1 + 4))), (60, 54, 48), 0.35, blur=8)
    ic.line([(x0 + 4, y0 + 2), (x1 - 4, y0 + 2)], 4, (255, 253, 246, 170))
    ic.outline(fp, 4, (60, 52, 44, 190))
    ic.outline(tp, 4, (60, 52, 44, 150))
    if wedges:
        ym = y0 - depth * 0.5
        xa, xb = x0 + shift * 0.5 + 10, x1 + shift * 0.5 - 6
        ic.line([(xa, ym + 1), (xb, ym - 1)], 7, (46, 36, 30, 230))  # split line on the top
        ic.line([(xb, ym), (x1 + shift * 0.5, y1 - depth * 0.3)], 6, (46, 36, 30, 220))  # running down the end
        for k in range(wedges):
            x = xa + (xb - xa) * (k + 0.6) / (wedges + 0.4)
            ic.poly([(x - 13, ym - 38), (x + 13, ym - 38), (x + 4, ym + 2), (x - 4, ym + 2)], "#6a686a", "#2c2a2c", edge=3)
            ic.line([(x - 11, ym - 36), (x + 1, ym - 36)], 4, (190, 190, 196, 220))


def loose_block(ic: Icon, cx: float, cy: float, w: float, h: float, depth: float, shift: float, deg: float) -> None:
    """Cut block lying loose on its skid, turned a little: lit top, veined front, rough sawn right end in
    shadow, lashed with a rope."""
    rot = lambda pts: ic.rotate(pts, (cx, cy), deg)  # noqa: E731
    hw = w / 2
    fp = rot([(-hw, -h), (hw, -h), (hw, 0), (-hw, 0)])
    tp = rot([(-hw + shift * 0.4, -h - depth), (hw + shift, -h - depth), (hw, -h), (-hw, -h)])
    ep = rot([(hw, -h), (hw + shift, -h - depth), (hw + shift, -depth * 0.8), (hw, 0)])
    ic.fill(ic.poly_mask(tp), TOP, "#d6cab4", (cy - h - depth, cy - h), noise=0.12, chroma=0.03)
    em = rough(ic, ep, "#7e7466", "#4c443a", cracks=0)
    lay, d = layer()  # saw striations on the rough end
    for k in range(9):
        p = rot([(hw + 2, -h + k * h / 9 + 6), (hw + shift, -h - depth + k * h / 9 + 8)])
        d.line(p, fill=(36, 30, 26, 120), width=3)
    composite(ic, lay, em)
    fm = ic.poly_mask(fp)
    ic.fill(fm, MARBLE, MARBLE_MID, (cx - hw - 40, cx + hw + 120), vertical=False, noise=0.12, chroma=0.03)
    veins(ic, fm, (cx - hw, cy - h, cx + hw, cy), 3)
    rust(ic, fm, cx - hw + 10, cx + hw - 10, cy - h, cy, 2, 0.6)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, cy - 30, SIZE, cy + 20))), (60, 54, 48), 0.3, blur=10)
    ic.line(rot([(-hw + 4, -h + 2), (hw - 4, -h + 2)]), 4, (255, 253, 246, 170))
    ic.outline(fp, 4, (60, 52, 44, 190))
    ic.outline(tp, 4, (60, 52, 44, 150))
    ic.outline(ep, 4, (40, 34, 28, 190))
    # rope lashing: over the top and down the front, loose end trailing to the ground
    for u in (-0.3, 0.32):
        x = hw * u * 2
        r = rot([(x + shift * 0.7, -h - depth), (x, -h), (x - 2, 0)])
        ic.line(r, 11, (40, 28, 16, 220))
        ic.line(r, 6, (168, 138, 92))
    end = rot([(hw * 0.64 - 2, 0)])[0]
    tail = [end, (end[0] + 30, end[1] + 18), (end[0] + 70, end[1] + 22), (end[0] + 96, end[1] + 12)]
    ic.line(tail, 10, (40, 28, 16, 220))
    ic.line(tail, 5, (168, 138, 92))


# ---- drawing ---------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.92
    ic.grade["mute"] = 0.86
    R = ic.random

    # ---- the hill: rises high on the left, falls away to the right, broken rocky crest
    hill = [(24, 905), (34, 700), (48, 480), (66, 320), (90, 220), (112, 150), (140, 118), (176, 132), (214, 108),
            (250, 126), (292, 112), (330, 128), (372, 122), (410, 150), (452, 146), (500, 176), (548, 178), (590, 214),
            (632, 240), (680, 296), (730, 330), (776, 388), (830, 424), (880, 470), (924, 506), (956, 566), (984, 640),
            (998, 730), (1004, 905)]
    hm = ic.poly_mask(hill)
    ic.fill(hm, ROCK, ROCK_DK, radial=(100, 80, 1100), noise=0.3, chroma=0.08)
    with ic.clipped(hm):
        for _ in range(30):  # weathering blotches, earth and grey rock
            bx, by = R.uniform(40, 990), R.uniform(100, 800)
            ic.shade(ic.poly_mask(ic.jitter(bx, by, R.uniform(18, 50), R.uniform(10, 28), 8, 0.3)),
                     (255, 240, 210) if R.random() < 0.35 else ((80, 60, 38) if R.random() < 0.6 else (120, 116, 108)),
                     0.2, blur=6)
        lay, d = layer()  # a few joints and cracks in the rock
        for _ in range(6):
            x, y = R.uniform(40, 990), R.uniform(160, 780)
            pts = [(x, y)]
            for _ in range(3):
                x, y = x + R.uniform(-16, 16), y + R.uniform(12, 24)
                pts.append((x, y))
            d.line(pts, fill=(44, 30, 20, 150), width=4, joint="curve")
        composite(ic, lay)
        # rough, unworked marble breaking through the slope beside the cut
        for x, y, rx, ry in ((74, 560, 46, 32), (112, 400, 40, 26), (830, 590, 58, 36), (900, 710, 48, 34)):
            pts = ic.jitter(x, y, rx, ry, 8, 0.2)
            rough(ic, pts, "#cfc2a8", "#857a68", cracks=1)
            ic.shade(ic.poly_mask([(x - rx, y), (x, y - ry), (x + rx * 0.3, y - ry * 0.4), (x - rx * 0.2, y + ry * 0.2)]),
                     (255, 250, 236), 0.22)
            ic.outline(pts, 3, (60, 48, 36, 150))
        rust(ic, hm, 40, 990, 200, 820, 10, 0.7)
        ic.shade(ic.mask("rectangle", (0, 700, SIZE, SIZE)), (40, 28, 18), 0.3, blur=40)
        ic.shade(ic.poly_mask([(0, 0), (420, 0), (0, 520)]), (240, 220, 180), 0.14, blur=60)

    # ---- earth and iron-stained overburden above the top bench
    ob = [(250, 236), (280, 214), (340, 206), (400, 196), (460, 204), (530, 200), (596, 222), (590, 228), (490, 246),
          (290, 246), (258, 238)]
    om = rough(ic, ob, "#7a5634", "#4a321e", cracks=3)
    rust(ic, om, 260, 590, 196, 246, 10, 1.3)
    lay, d = layer()  # roots
    for _ in range(7):
        x = R.uniform(290, 560)
        d.line([(x, 204), (x + R.uniform(-10, 10), 226), (x + R.uniform(-16, 16), 246)], fill=(40, 26, 14, 160), width=3)
    composite(ic, lay, om)

    # ---- three benches cut into the hill, the white area narrowing upward, staggered
    level(ic, 290, 500, 246, 380, 256, 590, 30, grooves=((310, 400),), chips=(True, False))
    level(ic, 256, 590, 410, 584, 160, 626, 48, grooves=((276, 360),), chips=(False, True))
    level(ic, 160, 626, 632, 812, 92, 740, 12, grooves=((370, 520),), chips=(True, True))

    # a block half cut free standing proud on the middle bench, split along the top with three wedges
    ic.shade(ic.mask("rectangle", (380, 606, 580, 636)), alpha=0.45, blur=10)
    ic.shade(ic.poly_mask([(530, 510), (580, 510), (600, 632), (530, 632)]), alpha=0.3, blur=12)
    standing_block(ic, 380, 530, 540, 630, depth=30, shift=18, wedges=3)

    # ---- quarry floor: ochre dust and marble chips
    floor = [(40, 960), (58, 812), (970, 812), (990, 960)]
    ic.poly(floor, "#a88c66", "#6e5638", noise=0.3, edge=0)
    lay, d = layer()
    for _ in range(90):
        cx, cy = R.uniform(70, 960), R.uniform(818, 955)
        r = R.uniform(4, 10)
        d.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=(232, 224, 208, R.randint(90, 180)))
    composite(ic, lay, ic.poly_mask(floor))
    ic.shade(ic.mask("rectangle", (60, 812, 960, 842)), (30, 20, 12), 0.5, blur=10)  # foot of the face
    ic.outline(floor, 4, (60, 44, 30, 170))

    # ---- iron drill bar and sledge leaning at the face
    timber(ic, (215, 905), (262, 730), 16)
    ic.rect((232, 700, 300, 744), "#5a585a", "#2e2c2e", edge=4)
    ic.line([(268, 900), (300, 700)], 14, IRON)
    ic.line([(271, 896), (302, 704)], 5, (130, 128, 130))

    # ---- loose cut block on a skid, turned slightly, roped; crowbar
    ic.shade(ic.mask("rectangle", (600, 890, 940, 940)), alpha=0.5, blur=14)
    timber(ic, (610, 918), (930, 906), 28)
    for ex in (610, 930):
        ic.rect((ex - 14, 898, ex + 14, 926), "#b08658", "#6e4c30", edge=4)
    loose_block(ic, 740, 902, 250, 104, 34, 30, -3.5)
    ic.shade(ic.poly_mask([(900, 780), (950, 800), (960, 900), (900, 900)]), alpha=0.35, blur=16)
    timber(ic, (918, 940), (986, 744), 16, "#7a7672", "#3c3a38")  # crowbar

    # ---- heap of marble chips and rubble, bottom left
    body = [(40, 965), (70, 880), (130, 830), (220, 820), (300, 860), (345, 965)]
    ic.poly(body, "#8e7a60", "#4e3e2c", noise=0.3, edge=4)
    for y, xs in ((850, (140, 205, 265)), (895, (90, 160, 230, 300)), (935, (70, 130, 200, 265, 325))):
        for x in xs:
            chunk(ic, x + R.uniform(-10, 10), y + R.uniform(-8, 8), R.uniform(26, 38))

    # ---- broken rocky crest: weathered outcrops breaking the skyline
    for x, y, rx, ry in ((176, 136, 40, 28), (338, 128, 38, 26), (470, 164, 34, 22), (620, 238, 30, 20),
                         (776, 386, 36, 24)):
        pts = ic.jitter(x, y, rx, ry, 7, 0.25)
        rough(ic, pts, "#b8a88c", "#6a5c4a", cracks=1)
        ic.shade(ic.poly_mask([(x - rx, y + 4), (x - rx * 0.3, y - ry), (x + rx * 0.4, y - ry * 0.7), (x, y + 2)]),
                 (255, 246, 226), 0.3)
        ic.shade(ic.poly_mask([(x, y + 2), (x + rx, y - ry * 0.2), (x + rx, y + ry), (x - rx * 0.2, y + ry)]),
                 (20, 14, 10), 0.3)
        ic.outline(pts, 4, (50, 40, 30, 190))

    # ---- scrub only along the crest
    for x, y, r in ((140, 128, 38), (214, 118, 36), (296, 124, 40), (412, 162, 36), (548, 190, 32), (680, 306, 36),
                    (830, 434, 36), (924, 516, 30)):
        scrub(ic, x, y, r)
