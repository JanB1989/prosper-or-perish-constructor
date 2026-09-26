"""Marble Saw Yard (marble_saw_yard): a water-driven frame saw sawing a white marble block into slabs.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/marble_saw_yard/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/marble_saw_yard

Composition: an open timber saw shed under a terracotta roof, its boarded back wall lit warmly from
the open front, a pulley block and a spare blade hanging inside. A heavy dark gang-saw frame hangs
from the tie beam on iron rods; five bright steel blades run down into dark kerfs in a big veined
marble block, with pale wet slurry streaking the face and pooling at its foot. An undershot water
wheel on the left dips its paddles into the leat with white splash and drives the frame through a
thick iron-strapped pitman rod. Near-white sawn slabs lean on a rack at the right (darker towards
the back) and lie stacked in front with grey sawn edges; a rough quarried block sits by the leat.
Second tier of the marble chain (after the Marble Quarry). Unlike vanilla sawmill (log saw, wheel on
the right) the wheel sits left and the load is white marble.
"""

import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 5
REFS = ("sawmill", "stone_quarry", "mason", "lumber_mill")

MARBLE = "#e6ddcc"
MARBLE_MID = "#bfb19a"
MARBLE_DK = "#8a7d6a"
TOP = "#efe7d6"
VEIN = (92, 96, 106)
WOOD, WOOD_DK = "#8a6240", "#4c3422"
STONE, STONE_DK = "#a08a70", "#665646"
W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
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
        if R.random() < 0.5 and len(pts) > 6:
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


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam: lit upper half, darker lower half, grain highlight, soft rim."""
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


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        gx = v + R.uniform(4, w - 4)
        d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(30, 44), width=(60, 120)) -> None:
    """Weathered ashlar face: per-block tint, soft bevels, grime, damp moss at the foot."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, base, dark, (x0 - 200, x1 + 200), vertical=False, noise=0.22, chroma=0.14)
    R = ic.random
    lay, d = layer()
    y = y0
    while y < y1:
        yb = min(y + R.randint(*course), y1)
        x = x0 - R.randint(0, width[0])
        while x < x1:
            xb = x + R.randint(*width)
            bx0, bx1 = max(x, x0), min(xb, x1)
            if bx1 - bx0 > 8:
                t = R.uniform(-1, 1)
                d.rectangle((bx0, y, bx1, yb), fill=(255, 240, 215, int(34 * t)) if t > 0 else (30, 22, 14, int(-52 * t)))
                d.line([(bx0 + 4, y + 4), (bx1 - 5, y + 4)], fill=(255, 246, 228, 70), width=4)
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
            x = xb
        y = yb
    composite(ic, lay, m)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - 50, x1, y1 + 20))), (22, 30, 20), 0.4, blur=16)
    for _ in range(int((x1 - x0) / 50)):
        mx, my = R.uniform(x0, x1), y1 - R.uniform(6, 40)
        blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(12, 30), R.uniform(6, 14), 8, 0.3)))
        ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)


def block(ic: Icon, x0: float, x1: float, y0: float, y1: float, depth: float = 40, shift: float = 22,
          vein_n: int | None = None) -> tuple[Image.Image, Image.Image]:
    """Squared marble block: front face and lit top, veins, bevels. Returns (front mask, top mask)."""
    tp = [(x0 + shift * 0.3, y0 - depth), (x1 + shift * 0.3, y0 - depth), (x1, y0), (x0, y0)]
    tm = ic.poly_mask(tp)
    ic.fill(tm, TOP, "#d8cdb8", (y0 - depth, y0), noise=0.12, chroma=0.03)
    fp = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    fm = ic.poly_mask(fp)
    ic.fill(fm, MARBLE, MARBLE_MID, (x0 - 60, x1 + 120), vertical=False, noise=0.12, chroma=0.03)
    veins(ic, tm, (x0, y0 - depth, x1, y0), 2, strength=0.7)
    veins(ic, fm, (x0, y0, x1, y1), vein_n or max(2, int((x1 - x0) / 60)))
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, y1 - 30, SIZE, y1 + 4))), (60, 54, 48), 0.3, blur=10)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (x0 + (x1 - x0) * 0.6, 0, SIZE, SIZE))), (52, 56, 72), 0.2, blur=30)
    ic.line([(x0 + 4, y0 + 2), (x1 - 4, y0 + 2)], 4, (255, 253, 246, 170))
    ic.outline(fp, 4, (60, 52, 44, 190))
    ic.outline(tp, 4, (60, 52, 44, 150))
    return fm, tm


def slab(ic: Icon, pts, lit: float = 1.0) -> None:
    """Thin sawn marble slab leaning or standing: near-white veined face, bright top edge, darker toward the
    foot. ``lit`` darkens slabs further back."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    c1 = tuple(int(v * lit) for v in (240, 234, 222))
    c2 = tuple(int(v * lit) for v in (206, 198, 182))
    ic.fill(m, c1, c2, (min(xs) - 20, max(xs) + 60), vertical=False, noise=0.1, chroma=0.02)
    veins(ic, m, (min(xs), min(ys), max(xs), max(ys)), 4, direction=65, strength=0.9)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, max(ys) - 60, SIZE, SIZE))), (60, 54, 46), 0.25, blur=16)
    ic.line([pts[0], pts[1]], 7, (255, 253, 246, 230))
    ic.outline(pts, 4, (60, 52, 44, 190))


def sawn_edge(ic: Icon, pts, lit: float = 1.0) -> None:
    """The sawn edge of a slab: grey, darker than the face, fine saw striations."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, tuple(int(v * lit) for v in (170, 162, 150)), tuple(int(v * lit) for v in (108, 100, 90)),
            (min(ys), max(ys)), noise=0.14, chroma=0.02)
    lay, d = layer()
    xs = [p[0] for p in pts]
    for y in range(int(min(ys)) + 10, int(max(ys)), 16):
        d.line([(min(xs), y), (max(xs), y + 4)], fill=(60, 56, 50, 70), width=2)
    composite(ic, lay, m)
    ic.outline(pts, 4, (50, 44, 38, 190))


def rough_block(ic: Icon, pts) -> None:
    """Quarried rough marble block: irregular, chipped, lit top-left facet, iron-stained."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, "#ddd3c0", "#8e8270", radial=(min(xs), min(ys), (max(xs) - min(xs)) * 1.3), noise=0.24, chroma=0.04)
    veins(ic, m, (min(xs), min(ys), max(xs), max(ys)), 2, strength=0.8)
    R = ic.random
    for _ in range(3):
        sx = R.uniform(min(xs) + 10, max(xs) - 10)
        ic.shade(ic.intersect(m, ic.poly_mask([(sx - 8, min(ys)), (sx + 8, min(ys)), (sx + 2, max(ys)), (sx - 2, max(ys))])),
                 (168, 94, 38), 0.3, blur=5)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (min(xs) + (max(xs) - min(xs)) * 0.55, 0, SIZE, SIZE))), (30, 26, 22),
             0.3, blur=10)
    ic.outline(pts, 4, (60, 52, 44, 190))


def wheel(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Undershot water wheel: paddles round a double rim, eight spokes, iron-bound hub; light upper left."""
    R = ic.random
    n = 14
    for k in range(n):  # paddle boards, sticking out of the rim
        a = 2 * math.pi * k / n + 0.1
        ca, sa = math.cos(a), math.sin(a)
        tx, ty = -sa, ca
        r0, r1, hw = r - 18, r + 30, 13
        pts = [(cx + ca * r0 + tx * hw, cy + sa * r0 + ty * hw), (cx + ca * r1 + tx * hw, cy + sa * r1 + ty * hw),
               (cx + ca * r1 - tx * hw, cy + sa * r1 - ty * hw), (cx + ca * r0 - tx * hw, cy + sa * r0 - ty * hw)]
        lit = 1.0 if (ca < 0.2 and sa < 0.3) else 0.72
        ic.poly(pts, tuple(int(v * lit) for v in (150, 108, 70)), tuple(int(v * lit) for v in (84, 58, 36)), edge=4)
    ring = ImageChops.subtract(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)),
                               ic.mask("ellipse", (cx - r + 26, cy - r + 26, cx + r - 26, cy + r - 26)))
    ic.fill(ring, "#b88456", "#5e3e24", radial=(cx - r * 0.7, cy - r * 0.7, r * 2.2), noise=0.2)
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 26, 16, 200), width=5))
    ic.overlay(lambda d: d.ellipse((cx - r + 26, cy - r + 26, cx + r - 26, cy + r - 26), outline=(40, 26, 16, 200), width=4))
    ic.overlay(lambda d: d.arc((cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), 170, 280, fill=(255, 225, 180, 90), width=5))
    for k in range(8):
        a = math.pi * k / 4 + 0.3
        timber(ic, (cx + math.cos(a) * 30, cy + math.sin(a) * 30), (cx + math.cos(a) * (r - 20), cy + math.sin(a) * (r - 20)),
               18, "#a87a4e", "#5e3e26")
    ic.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), "#8a6440", "#4a3220", edge=5)
    ic.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), "#5c5a5c", "#2c2a2c", edge=4)


def coppi(ic: Icon, eave: float, ridge: float, ex0: float, ex1: float, rx0: float, rx1: float,
          col: float = 34) -> Image.Image:
    """Roman channel-tile roof plane: columns of round tiles running eave to ridge, per-column tone, lit
    left flank and shadowed gutter per column, staggered overlaps, round tile ends along the eave."""
    pts = [(ex0, eave), (ex1, eave), (rx1, ridge), (rx0, ridge)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#c07a52", "#8a4a30", (ridge, eave), noise=0.18, chroma=0.12)
    R = ic.random
    lay, d = layer()
    n = int((ex1 - ex0) / col)
    for k in range(n + 1):
        u0, u1 = k / n, (k + 1) / n
        b0, b1 = ex0 + (ex1 - ex0) * u0, ex0 + (ex1 - ex0) * u1
        t0, t1 = rx0 + (rx1 - rx0) * u0, rx0 + (rx1 - rx0) * u1
        t = R.uniform(-1, 1)
        d.polygon([(b0, eave), (b1, eave), (t1, ridge), (t0, ridge)],
                  fill=(255, 210, 160, int(30 * t)) if t > 0 else (40, 16, 6, int(-45 * t)))
        d.line([(b0, eave), (t0, ridge)], fill=(46, 20, 10, 170), width=7)  # gutter between tile columns
        d.line([(b0 + col * 0.3, eave), (t0 + col * 0.3, ridge)], fill=(255, 214, 170, 90), width=6)  # lit flank
        y = ridge + R.uniform(0, 34)
        while y < eave - 10:
            f = (y - ridge) / (eave - ridge)
            xa = t0 + (b0 - t0) * f
            xb = t1 + (b1 - t1) * f
            d.arc((xa + 3, y - 10, xb - 3, y + 10), 20, 160, fill=(50, 22, 10, 120), width=4)
            y += R.uniform(36, 48)
    composite(ic, lay, m)
    for _ in range(10):  # lichen and soot blotches
        bx, by = R.uniform(ex0, ex1), R.uniform(ridge + 20, eave - 10)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(bx, by, R.uniform(16, 36), R.uniform(8, 16), 8, 0.3))),
                 (150, 150, 90) if R.random() < 0.5 else (40, 24, 14), 0.22, blur=5)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (0, eave - 40, SIZE, eave))), alpha=0.18, blur=12)
    for k in range(n):  # tile ends along the eave
        cx = ex0 + (ex1 - ex0) * (k + 0.5) / n
        ic.ellipse((cx - col * 0.42, eave - 12, cx + col * 0.42, eave + 12), "#b06a46", "#5e2e1c", edge=3)
        ic.draw.ellipse((cx - col * 0.18, eave - 4, cx + col * 0.18, eave + 6), fill=(40, 18, 10, 255))
    ic.outline(pts, 5)
    return m


# ---- drawing ---------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.86
    ic.grade["mute"] = 0.84
    R = ic.random

    # ---- yard ground
    ground = [(300, 952), (330, 810), (990, 810), (1006, 952)]
    ic.poly(ground, "#a88c66", "#6e5638", noise=0.3, edge=4)
    lay, d = layer()
    for _ in range(60):
        cx, cy = R.uniform(330, 990), R.uniform(816, 948)
        r = R.uniform(4, 9)
        d.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=(232, 224, 208, R.randint(80, 170)))
    composite(ic, lay, ic.poly_mask(ground))

    # ---- open saw shed: boarded back wall lit warmly from the open front, tie beam
    SX0, SX1, EAVE = 350, 800, 352
    back = planks(ic, [(SX0, EAVE), (SX1, EAVE), (SX1, 812), (SX0, 812)], "#a07a52", "#6a4c30", board=30)
    ic.shade(ic.intersect(back, ic.mask("rectangle", (0, EAVE, SIZE, EAVE + 130))), (0, 0, 0), 0.4, blur=34)
    ic.shade(ic.intersect(back, ic.mask("ellipse", (SX0 - 80, 520, SX1 + 80, 1060))), (255, 206, 146), 0.3, blur=50)
    ic.shade(ic.intersect(back, ic.mask("rectangle", (SX0, EAVE, SX0 + 60, 812))), (0, 0, 0), 0.25, blur=20)
    # a spare saw blade and a hook hanging on the back wall, a pulley block on the tie beam
    ic.line([(376, 430), (376, 700)], 7, (40, 30, 22))
    ic.line([(372, 440), (372, 690)], 4, (196, 198, 204))
    ic.line([(760, EAVE + 30), (760, 450)], 6, (60, 46, 30))
    ic.ellipse((736, 440, 784, 488), "#6a6668", "#2e2c2e", edge=4)
    ic.ellipse((754, 458, 766, 470), "#1e1c1c", "#1e1c1c", edge=0)
    ic.line([(760, 488), (760, 540), (748, 556)], 6, (52, 50, 52))
    timber(ic, (SX0 - 10, EAVE + 16), (SX1 + 10, EAVE + 16), 30, "#7a5436", "#3e2a18")  # tie beam

    # ---- marble block on its bed
    BX0, BX1, BY0, BY1 = 440, 730, 640, 818
    timber(ic, (BX0 - 30, 830), (BX1 + 40, 830), 30)
    fm, tm = block(ic, BX0, BX1, BY0, BY1, depth=44, vein_n=5)
    kerfs = [BX0 + (BX1 - BX0) * f for f in (0.14, 0.32, 0.5, 0.68, 0.86)]
    for x in kerfs:  # dark grooves cut into the top and down the face
        ic.line([(x + 7, BY0 - 44), (x + 1, BY0), (x + 1, BY0 + 86)], 9, (34, 30, 28, 240))
        ic.line([(x + 7, BY0 + 2), (x + 7, BY0 + 86)], 3, (255, 252, 244, 150))
    # pale wet slurry and marble dust running down the face and pooling at its foot
    for x in kerfs:
        ln = R.uniform(90, 170)
        streak = [(x - 10, BY0 + 60), (x + 14, BY0 + 60), (x + 18, BY0 + 60 + ln), (x - 6, BY0 + 60 + ln)]
        ic.shade(ic.intersect(fm, ic.poly_mask(streak)), (236, 236, 230), 0.55, blur=6)
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (BX0, BY1 - 40, BX1, BY1))), (226, 228, 224), 0.35, blur=10)
    pool = ic.poly_mask(ic.jitter(BX0 + 90, 858, 150, 18, 12, 0.12))  # milky slurry pooled on the ground
    ic.shade(pool, (214, 216, 210), 0.8, blur=5)
    ic.shade(ic.poly_mask(ic.jitter(BX0 + 70, 852, 90, 6, 8, 0.2)), (255, 255, 255), 0.5, blur=3)
    ic.shade(ic.mask("rectangle", (BX0 - 10, BY1 - 6, BX0 + 40, 860)), (226, 228, 224), 0.45, blur=8)  # dribble over the bed

    # ---- gang-saw frame: heavy dark timber rectangle hung from the tie beam, five steel blades in the kerfs
    FT, FB = 468, 590
    FX0, FX1 = BX0 - 44, BX1 + 64
    for hx in (FX0 + 20, FX1 - 20):  # iron hangers
        ic.line([(hx, EAVE + 26), (hx, FT + 10)], 11, IRON)
        ic.line([(hx - 3, EAVE + 26), (hx - 3, FT + 10)], 4, (150, 148, 150))
    for x in kerfs:  # blades
        ic.line([(x + 10, FT + 20), (x + 10, BY0 - 30)], 9, (40, 40, 44))
        ic.line([(x + 6, FT + 20), (x + 6, BY0 - 30)], 5, (214, 216, 222))
    dark, darker = "#5a3820", "#24160a"
    ic.shade(ic.mask("rectangle", (FX0 + 20, FT + 10, FX1 + 30, FB + 40)), alpha=0.3, blur=16)  # frame shadow on the wall
    timber(ic, (FX0, FT), (FX1, FT), 48, dark, darker)
    timber(ic, (FX0, FB), (FX1, FB), 40, dark, darker)
    timber(ic, (FX0 + 18, FT - 22), (FX0 + 18, FB + 20), 44, dark, darker)
    timber(ic, (FX1 - 18, FT - 22), (FX1 - 18, FB + 20), 44, dark, darker)
    ic.line([(FX0 - 2, FT - 22), (FX1 + 2, FT - 22)], 4, (255, 214, 160, 120))  # lit top arris
    for x in kerfs:  # blades pass in front of the lower rail, wedged in iron keys
        ic.line([(x + 10, FB - 20), (x + 10, BY0 - 30)], 9, (40, 40, 44))
        ic.line([(x + 6, FB - 20), (x + 6, BY0 - 30)], 5, (214, 216, 222))
        ic.rect((x - 2, FB - 26, x + 18, FB - 8), "#5c5a5c", "#2c2a2c", edge=3)
    ic.shade(ic.intersect(tm, ic.mask("rectangle", (BX0 - 40, BY0 - 50, BX1 + 60, BY0))), alpha=0.3, blur=10)

    # ---- posts and roof
    for px in (SX0, SX1):
        timber(ic, (px, EAVE), (px, 818), 34, "#946a44", "#553a24")
    coppi(ic, EAVE + 14, 176, SX0 - 80, SX1 + 80, SX0 - 16, SX1 + 16)
    ic.shade(ic.poly_mask([(SX0 - 80, EAVE + 14), (SX0 + 140, EAVE + 14), (SX0 + 180, 176), (SX0 - 16, 176)]),
             (255, 230, 190), 0.12, blur=30)
    ic.rect((SX0 - 28, 158, SX1 + 28, 184), "#a8603e", "#6a3a26", edge=4)  # ridge tiles
    ic.line([(SX0 - 20, 162), (SX1 + 20, 162)], 4, (255, 214, 170, 110))
    ic.shade(ic.mask("rectangle", (SX0, EAVE + 26, SX1, EAVE + 70)), alpha=0.4, blur=10)

    # ---- leat and undershot water wheel on the left, paddles dipping into the race
    WX, WY, WR = 196, 548, 180
    ic.fill(ic.mask("rectangle", (20, 690, 370, 742)), W_LIGHT, W_DEEP, (680, 760), noise=0.08)  # race behind the wheel
    wheel(ic, WX, WY, WR)
    # pitman rod from the crank on the wheel shaft to the saw frame
    ic.ellipse((WX + 24, WY - 74, WX + 76, WY - 22), "#6a6668", "#353335", edge=4)
    timber(ic, (WX + 50, WY - 48), (FX0 + 20, FB - 6), 32, "#9a6e46", "#4a3020")
    for t in (0.2, 0.8):  # iron straps on the rod
        x = WX + 50 + (FX0 + 20 - WX - 50) * t
        y = WY - 48 + (FB - 6 - WY + 48) * t
        ic.line([(x - 6, y - 18), (x + 6, y + 18)], 7, IRON)
    ic.ellipse((FX0 + 6, FB - 20, FX0 + 34, FB + 8), "#6a6668", "#353335", edge=3)
    # water over the lower wheel: translucent so the dipping paddles still show, white churn at the paddles
    water = ic.mask("rectangle", (20, 704, 372, 772))
    lay, d = layer()
    d.rectangle((20, 704, 372, 772), fill=(60, 128, 150, 200))
    composite(ic, lay, water)
    ic.shade(ic.intersect(water, ic.mask("rectangle", (0, 704, SIZE, 720))), (200, 232, 240), 0.5, blur=4)
    lay, d = layer()
    for _ in range(16):
        x, y = R.uniform(20, 360), R.uniform(724, 766)
        L = R.uniform(24, 60)
        d.line([(x, y), (x + L, y)], fill=(225, 240, 244, 160), width=4)
    composite(ic, lay, water)
    for sx in (WX - 118, WX - 40, WX + 40, WX + 118):  # splash where the paddles strike
        lay, d = layer()
        for _ in range(9):
            r = R.uniform(8, 18)
            x, y = sx + R.uniform(-30, 30), 706 + R.uniform(-22, 10)
            d.ellipse((x - r * 1.3, y - r * 0.8, x + r * 1.3, y + r * 0.8), fill=(244, 250, 250, 235))
        for _ in range(6):  # thrown droplets
            r = R.uniform(3, 6)
            x, y = sx + R.uniform(-40, 40), 690 + R.uniform(-46, -8)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(236, 246, 248, 220))
        composite(ic, lay.filter(ImageFilter.GaussianBlur(1.2)))
    ashlar(ic, (14, 770, 372, 900))
    ic.fill(ic.mask("rectangle", (8, 752, 378, 776)), "#c2ae90", "#94806a", (752, 776), noise=0.18)  # coping
    ic.shade(ic.mask("rectangle", (8, 776, 378, 792)), alpha=0.45, blur=6)
    ic.outline([(8, 752), (378, 752), (378, 900), (14, 900)], 4, (60, 44, 30, 170))

    # ---- a rough quarried block brought down from the quarry, by the leat
    ic.shade(ic.mask("rectangle", (240, 920, 400, 956)), alpha=0.45, blur=10)
    rough_block(ic, [(252, 950), (246, 880), (268, 846), (330, 836), (382, 850), (398, 900), (392, 950)])

    # ---- sawn slabs leaning on a rack, right: lighter in front, darker toward the back
    timber(ic, (840, 915), (905, 540), 18)
    for k, (x, top, lit) in enumerate(((872, 566, 0.78), (846, 594, 0.89), (814, 620, 1.0))):
        sawn_edge(ic, [(x + 150, top + 10), (x + 168, top + 18), (x + 136, 918), (x + 118, 918)], lit)
        slab(ic, [(x + 58, top), (x + 150, top + 10), (x + 118, 918), (x - 6, 918)], lit)
        ic.shade(ic.poly_mask([(x + 118, 918), (x + 150, top + 10), (x + 176, top + 40), (x + 150, 918)]), alpha=0.28,
                 blur=10)

    # ---- stack of slabs lying in front: thin sawn edges, veined top slab
    ic.shade(ic.mask("rectangle", (556, 900, 826, 944)), alpha=0.5, blur=10)
    for k, (y, x0, x1) in enumerate(((922, 562, 798), (900, 570, 790), (878, 560, 786))):
        sawn_edge(ic, [(x0, y - 20), (x1, y - 20), (x1, y), (x0, y)], 1.12 - k * 0.04)
        ic.line([(x0 + 4, y - 19), (x1 - 4, y - 19)], 3, (255, 253, 246, 170))
    tp = [(574, 818), (818, 818), (786, 858), (560, 858)]
    tpm = ic.poly_mask(tp)
    ic.fill(tpm, "#f2ede2", "#d6cebe", (818, 858), noise=0.1, chroma=0.02)
    veins(ic, tpm, (560, 818, 818, 858), 3, direction=10, strength=0.9)
    ic.outline(tp, 4, (60, 52, 44, 190))
