"""Stone Dressing Yard (stone_quarry_improved): masons' lodge, derrick crane and dressed blocks at a worked face.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/stone_quarry_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/stone_quarry_improved

Composition: a warm limestone crag behind with a broken outline, bedding-plane ledges, moss and a
sawn bench cut into its foot, shaded under the overhanging lip. In front of it a heavy timber derrick
(thick mast with iron cap, boom, topping lift) hoists a honey-coloured block on a hook and lewis; the
hoist rope runs back to a winch drum with spokes, rope turns and a crank at the mast foot. On the
right a masons' lodge with a blue-grey stone-slate roof, rubble end wall and an open bay where a
block lies on the banker with mallet and chisel. Dressed ashlar blocks with drafted margins are
stacked in front. Upgrade of vanilla stone_quarry (treadwheel crane over rough grey blocks): here
the crane is a winch derrick, the stone is squared and tooled, and the lodge is the main structure.
"""

import math

from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 17
REFS = ("stone_quarry", "mason", "clay_pit", "construction_center")

HONEY = "#d0b485"        # dressed buff limestone, lit face
HONEY_DK = "#8e764e"
HONEY_TOP = "#e8d6b0"
ROCK, ROCK_DK = "#a08c70", "#463a2c"
WOOD, WOOD_DK = "#8a6240", "#4c3422"
SLATE, SLATE_DK = "#868c96", "#40464f"
IRON = (52, 50, 52)
ROPE = (150, 124, 84)


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


def rope(ic: Icon, pts, width: int = 7) -> None:
    ic.line(pts, width + 4, (40, 28, 16, 220))
    ic.line(pts, width, ROPE)


def dressed(ic: Icon, x0: float, x1: float, y0: float, y1: float, depth: float = 30, shift: float = 16,
            lit: float = 1.0) -> None:
    """Dressed ashlar block: lit top, front face with a smooth drafted margin and tooled centre,
    crisp arrises, darker foot."""
    def k(c):
        c = c.lstrip("#")
        return tuple(int(int(c[i:i + 2], 16) * lit) for i in (0, 2, 4))

    tp = [(x0 + shift, y0 - depth), (x1 + shift, y0 - depth), (x1, y0), (x0, y0)]
    ic.fill(ic.poly_mask(tp), k(HONEY_TOP), k("#d4b680"), (y0 - depth, y0), noise=0.12, chroma=0.05)
    if shift > 0:  # right end face, in shade
        ic.poly([(x1, y0), (x1 + shift, y0 - depth), (x1 + shift, y1 - depth), (x1, y1)], k("#8e6c40"), k("#5e4628"),
                edge=0)
    fp = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    fm = ic.poly_mask(fp)
    ic.fill(fm, k(HONEY), k(HONEY_DK), (x0 - 40, x1 + 160), vertical=False, noise=0.26, chroma=0.08)
    R = ic.random
    t = R.uniform(-1, 1)  # each block from a slightly different bed
    ic.shade(fm, (255, 240, 210) if t > 0 else (60, 44, 24), abs(t) * 0.12)
    m = 10
    inner = ic.mask("rectangle", (x0 + m, y0 + m, x1 - m, y1 - m))
    lay, d = layer()
    for _ in range(int((x1 - x0) * (y1 - y0) / 260)):  # pecked (pointed) field
        px, py = R.uniform(x0, x1), R.uniform(y0, y1)
        r = R.uniform(2, 4)
        d.ellipse((px - r, py - r, px + r, py + r), fill=(70, 50, 26, R.randint(50, 110)))
        d.ellipse((px - r - 2, py - r - 3, px + r - 2, py - 1), fill=(255, 244, 216, R.randint(20, 60)))
    composite(ic, lay, inner)
    ic.shade(ic.intersect(fm, ic.mask("ellipse", (x0 + (x1 - x0) * 0.3, y0 + (y1 - y0) * 0.4, x1 + 40, y1 + 40))),
             (40, 30, 16), 0.16, blur=14)
    ic.line([(x0 + 4, y0 + 2), (x1 - 3, y0 + 2)], 4, (255, 240, 205, 180))
    ic.line([(x0 + 2, y0 + 3), (x0 + 2, y1 - 3)], 3, (255, 240, 205, 110))
    ic.shade(ic.intersect(fm, ic.mask("rectangle", (0, y1 - 18, SIZE, y1 + 2))), (40, 28, 14), 0.3, blur=6)
    ic.outline(fp, 4, (54, 38, 22, 200))
    ic.outline(tp, 4, (54, 38, 22, 150))


def slates(ic: Icon, pts, eave: float, ridge: float) -> Image.Image:
    """Stone-slate roof plane: courses shrinking towards the ridge, slates of uneven width and tone,
    shadow under each course, lichen."""
    m = ic.poly_mask(pts)
    ic.fill(m, "#969ca6", SLATE_DK, (ridge, eave), noise=0.18, chroma=0.10)
    R = ic.random
    lay, d = layer()
    y = eave
    course = 40
    while y > ridge:
        y0 = y - course
        x = -R.uniform(0, 60)
        while x < SIZE:
            w = R.uniform(38, 70)
            t = R.uniform(-1, 1)
            d.rectangle((x, y0, x + w, y), fill=(250, 240, 220, int(40 * t)) if t > 0 else (20, 18, 14, int(-60 * t)))
            d.line([(x, y0 + 4), (x + R.uniform(-3, 3), y - 2)], fill=(34, 30, 26, 150), width=4)
            x += w
        d.rectangle((0, y - 10, SIZE, y), fill=(24, 20, 16, 110))  # shadow under the course above
        d.line([(0, y0 + 2), (SIZE, y0 + 2)], fill=(255, 248, 230, 50), width=3)
        y = y0
        course = max(28, course - 2)
    composite(ic, lay, m)
    for _ in range(12):
        bx, by = R.uniform(min(p[0] for p in pts), max(p[0] for p in pts)), R.uniform(ridge + 10, eave - 10)
        ic.shade(ic.intersect(m, ic.poly_mask(ic.jitter(bx, by, R.uniform(12, 30), R.uniform(6, 14), 8, 0.3))),
                 (170, 168, 96), 0.25, blur=4)
    ic.outline(pts, 5)
    return m


def rubble(ic: Icon, box, base="#a89a82", dark="#6a5e4c") -> Image.Image:
    """Coursed rubble wall: irregular stones shaded as forms, dark mortar between."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, "#5a5044", "#3a3228", noise=0.2)
    R = ic.random
    y = y0
    while y < y1:
        h = R.uniform(26, 40)
        x = x0 - R.uniform(0, 30)
        while x < x1:
            w = R.uniform(34, 70)
            cx, cy = x + w / 2, y + h / 2
            pts = ic.jitter(cx, cy, w / 2 - 3, h / 2 - 3, 8, 0.12)
            sm = ic.intersect(m, ic.poly_mask(pts))
            t = R.uniform(0.85, 1.12)
            c1 = tuple(min(255, int(v * t)) for v in (int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)))
            ic.fill(sm, c1, dark, radial=(cx - w * 0.4, cy - h * 0.5, w * 1.1), noise=0.18)
            x += w
        y += h
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return m


def lbench(ic: Icon, x0: float, x1: float, top: float, face: float, foot: float) -> None:
    """Sawn bench of bedded limestone: lit top strip, riser with horizontal beds, faint drill traces,
    shadow under the edge, cooler shade to the right."""
    R = ic.random
    ic.fill(ic.poly_mask([(x0 + 8, top), (x1, top), (x1, face), (x0, face)]), "#c9b48a", "#e6d4ae", (top, face),
            noise=0.14)
    rm = ic.mask("rectangle", (x0, face, x1, foot))
    ic.fill(rm, "#d4bc8c", "#9a8260", (x0 - 60, x1 + 160), vertical=False, noise=0.2, chroma=0.06)
    for _ in range(int((x1 - x0) / 60)):  # beds of slightly different tone, soft
        bx, by = R.uniform(x0, x1), R.uniform(face + 30, foot - 20)
        ic.shade(ic.intersect(rm, ic.poly_mask(ic.jitter(bx, by, R.uniform(40, 80), R.uniform(16, 30), 9, 0.25))),
                 (255, 240, 210) if R.random() < 0.5 else (70, 52, 30), 0.12, blur=10)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, face, SIZE, foot))), (48, 52, 66), 0.22,
             blur=40)
    ic.shade(ic.intersect(rm, ic.mask("rectangle", (0, face, SIZE, face + 26))), (40, 30, 20), 0.45, blur=8)
    ic.line([(x0 + 4, face + 1), (x1, face + 1)], 4, (255, 246, 222, 140))
    ic.outline([(x0, face), (x1, face), (x1, foot), (x0, foot)], 4, (60, 46, 30, 170))


# ---- drawing ---------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.84
    ic.grade["mute"] = 0.84

    # ---- worked quarry face behind: a broken limestone crag with moss, a sawn bench cut into its foot
    face = [(24, 900), (18, 800), (34, 740), (26, 660), (52, 600), (44, 530), (78, 480), (70, 420), (110, 380),
            (124, 318), (168, 292), (194, 246), (244, 234), (268, 198), (318, 190), (344, 164), (392, 178),
            (420, 160), (462, 196), (500, 192), (530, 226), (574, 240), (604, 286), (640, 310), (662, 360),
            (670, 900)]
    fmask = ic.poly_mask(face)
    ic.fill(fmask, ROCK, ROCK_DK, radial=(420, 140, 600), noise=0.3, chroma=0.10)
    R = ic.random
    with ic.clipped(fmask):
        for _ in range(12):  # weathering: warm stains and grey patches
            bx, by = R.uniform(40, 650), R.uniform(200, 480)
            ic.shade(ic.poly_mask(ic.jitter(bx, by, R.uniform(24, 56), R.uniform(12, 26), 8, 0.3)),
                     (120, 84, 50) if R.random() < 0.5 else (150, 146, 136), 0.18, blur=8)
        # bedding planes: a lit ledge top above each crack, a shadow under the ledge
        for yb in (292, 378):
            pts = [(0, yb + R.uniform(-8, 8))]
            for x in range(60, 720, 60):
                pts.append((x, yb + R.uniform(-14, 14) + (x - 300) * 0.04))
            top = [(p[0], p[1] - 4) for p in pts] + [(p[0], p[1] - 24) for p in reversed(pts)]
            ic.shade(ic.poly_mask(top), (255, 238, 205), 0.34, blur=4)
            under = pts + [(p[0], p[1] + 34) for p in reversed(pts)]
            ic.shade(ic.poly_mask(under), (20, 14, 8), 0.4, blur=6)
            for k in range(0, len(pts) - 1, 1):  # the crack itself, broken
                if R.random() < 0.8:
                    ic.line([pts[k], pts[k + 1]], 7, (34, 24, 16, 230))
            for k in range(2):  # a few vertical joints between the beds
                jx = R.uniform(80, 620)
                ic.line([(jx, yb + 4), (jx + R.uniform(-10, 10), yb + 70)], 5, (40, 30, 20, 170))
        for _ in range(5):  # lit facets on the upper right of the knobs
            fx, fy = R.uniform(150, 600), R.uniform(210, 440)
            ic.shade(ic.poly_mask([(fx, fy), (fx + 60, fy - 20), (fx + 80, fy + 20), (fx + 20, fy + 30)]),
                     (255, 240, 210), 0.18, blur=4)
        for _ in range(14):  # moss on the ledges
            mx, my = R.uniform(60, 640), R.choice((260, 346, 440)) + R.uniform(-10, 10)
            ic.shade(ic.poly_mask(ic.jitter(mx, my, R.uniform(14, 34), R.uniform(6, 12), 8, 0.3)), (96, 116, 52), 0.5,
                     blur=3)
        ic.poly([(96, 470), (150, 486), (150, 770), (40, 770), (60, 560)], "#5c4c3a", "#30261c", edge=0,
                noise=0.25)  # left cut wall, in shadow
        lbench(ic, 150, 680, 486, 516, 770)
        # broken top edge of the cut: rough rock overhanging the sawn face, casting a shadow on it
        ic.shade(ic.mask("rectangle", (150, 486, 700, 540)), (20, 14, 8), 0.4, blur=12)
        for x0, x1, dy in ((150, 260, 34), (330, 420, 22), (480, 560, 40)):
            lip = [(x0, 484), (x1, 484), (x1 - 10, 484 + dy * 0.5), ((x0 + x1) / 2, 484 + dy), (x0 + 8, 484 + dy * 0.6)]
            ic.shade(ic.poly_mask([(p[0] + 10, p[1] + 16) for p in lip]), alpha=0.45, blur=8)
            ic.fill(ic.poly_mask(lip), "#8c7a62", "#4e4234", noise=0.25)
        ic.poly([(20, 770), (700, 770), (700, 900), (20, 900)], "#7a6c54", "#4a4032", edge=0, noise=0.3)
        ic.shade(ic.mask("rectangle", (0, 770, SIZE, 800)), alpha=0.45, blur=8)
    ic.outline(face)
    for x, y, r in ((244, 244, 46), (344, 176, 40), (420, 170, 38), (530, 234, 36), (124, 326, 34)):
        ic.fill(ic.poly_mask(ic.jitter(x, y, r, r * 0.6, 10, 0.2)), "#7e8a48", "#3c4620",
                radial=(x - r, y - r, r * 2), noise=0.3)

    # ---- masons' lodge, right: rubble end wall, open bay with the banker, stone-slate roof
    LX0, LX1, EAVE, RIDGE = 600, 990, 470, 250
    wall = rubble(ic, (LX0, EAVE, 740, 860))
    ic.shade(ic.intersect(wall, ic.mask("rectangle", (LX0, EAVE, 740, EAVE + 70))), alpha=0.45, blur=12)
    ic.window(648, 560, 694, 612)
    bay = ic.mask("rectangle", (740, EAVE, LX1 - 10, 860))
    ic.fill(bay, "#4a3826", "#241a10", (EAVE, 860), noise=0.15)
    ic.shade(ic.mask("rectangle", (740, EAVE, LX1, EAVE + 90)), alpha=0.4, blur=16)
    # tools hanging on the back wall
    ic.line([(800, 530), (800, 600)], 7, (140, 104, 66))
    ic.rect((784, 594, 816, 620), "#6a6668", "#353335", edge=3)  # mallet head
    ic.line([(840, 530), (846, 600)], 5, (150, 150, 156))
    ic.line([(870, 530), (874, 590)], 5, (150, 150, 156))
    # banker: a stone block on a timber trestle, a block on it half dressed
    timber(ic, (780, 790), (780, 862), 18)
    timber(ic, (940, 790), (940, 862), 18)
    ic.rect((764, 770, 958, 800), "#a07648", "#5e4228", edge=4)
    dressed(ic, 800, 920, 700, 770, depth=22, shift=10)
    ic.shade(ic.mask("rectangle", (800, 700, 860, 770)), (60, 50, 40), 0.2, blur=6)
    # the mallet resting on the banker
    ic.line([(930, 752), (975, 700)], 9, (140, 104, 66))
    ic.ellipse((906, 736, 954, 776), "#9c7a52", "#5e4228", edge=4)
    for px in (740, LX1 - 10):
        timber(ic, (px, EAVE), (px, 866), 30, "#946a44", "#553a24")
    slates(ic, [(LX0 - 40, EAVE + 10), (LX1 + 24, EAVE + 10), (LX1 - 16, RIDGE), (LX0 + 10, RIDGE)], EAVE + 10, RIDGE)
    ic.rect((LX0 + 2, RIDGE - 20, LX1 - 6, RIDGE + 6), "#7a766e", "#4c4844", edge=4)  # ridge stones
    ic.shade(ic.mask("rectangle", (LX0 - 40, RIDGE, LX0 + 140, EAVE)), (255, 244, 220), 0.1, blur=30)
    ic.shade(ic.mask("rectangle", (LX0, EAVE + 10, LX1, EAVE + 44)), alpha=0.4, blur=9)
    # chimney of the lodge's forge (tools are sharpened here)
    ic.rect((650, 196, 700, 300), "#9a8c7a", "#6a5f52", vertical=False, edge=4)
    ic.rect((642, 184, 708, 202), "#877a69", "#5e544a", edge=4)

    # ---- ground of the yard
    ground = [(20, 960), (40, 860), (1000, 860), (1008, 960)]
    ic.poly(ground, "#a6916a", "#6c5a3c", noise=0.3, edge=4)
    lay, d = layer()
    for _ in range(70):
        cx, cy = ic.random.uniform(40, 1000), ic.random.uniform(866, 956)
        r = ic.random.uniform(4, 9)
        d.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=(226, 206, 160, ic.random.randint(80, 170)))
    composite(ic, lay, ic.poly_mask(ground))
    ic.shade(ic.mask("rectangle", (40, 860, 1000, 890)), (30, 22, 12), 0.45, blur=10)

    # ---- derrick crane: thick mast and boom, winch drum at the mast foot, block on hook and lewis
    MX, MTOP, MFOOT = 170, 176, 900
    BTIP = (566, 300)
    WX, WY, WR = MX + 96, 800, 66  # winch drum
    ic.shade(ic.mask("rectangle", (MX - 40, 880, WX + 90, 920)), alpha=0.4, blur=12)
    timber(ic, (MX - 40, 890), (WX + 80, 890), 26)  # sill
    timber(ic, (WX, WY), (WX, 890), 24)  # axle post
    timber(ic, (WX + 50, 890), (WX, WY + 20), 18)  # brace
    timber(ic, (MX, MFOOT), (MX, MTOP), 52, "#c09060", "#4a3020")
    ic.line([(MX - 14, MTOP + 20), (MX - 14, MFOOT - 10)], 5, (255, 226, 180, 130))
    ic.rect((MX - 32, MTOP - 16, MX + 32, MTOP + 12), "#6a6668", "#2e2c2e", edge=4)  # iron cap
    rope(ic, [(MX + 12, MTOP + 4), (BTIP[0] - 12, BTIP[1] - 8)], 6)  # topping lift
    timber(ic, (MX + 24, 850), BTIP, 44, "#c09060", "#4a3020")
    ic.ellipse((BTIP[0] - 24, BTIP[1] - 22, BTIP[0] + 24, BTIP[1] + 26), "#6a6668", "#2e2c2e", edge=4)  # sheave
    ic.ellipse((BTIP[0] - 7, BTIP[1] - 5, BTIP[0] + 7, BTIP[1] + 9), "#1e1c1c", "#1e1c1c", edge=0)
    # hoist rope: down to the hook, and back along the boom to the drum
    HX = BTIP[0] + 14
    rope(ic, [(BTIP[0] - 10, BTIP[1] + 22), (WX + 6, WY - WR + 4)], 6)
    rope(ic, [(HX, BTIP[1] + 20), (HX, 408)], 7)
    # the block: lewis set in its top, hook through the lewis ring
    dressed(ic, 488, 636, 500, 590, depth=26, shift=14)
    LX = 568
    ic.rect((LX - 12, 474, LX + 12, 490), "#4a484a", "#1e1c1e", edge=3)  # lewis in the block
    ic.line([(LX, 474), (LX, 456)], 8, (30, 28, 30))
    ic.overlay(lambda d: d.ellipse((LX - 14, 434, LX + 14, 460), outline=(24, 22, 24, 255), width=9))  # lewis ring
    hook = [(HX, 406), (HX, 428), (HX - 2, 446), (LX, 450), (LX - 8, 436)]
    ic.line(hook, 13, (24, 22, 24))
    ic.line([(HX - 3, 408), (HX - 3, 428)], 4, (150, 148, 152))
    ic.ellipse((HX - 11, 396, HX + 11, 416), "#5c5a5c", "#1e1c1e", edge=3)  # hook block
    ic.shade(ic.mask("rectangle", (488, 900, 640, 930)), alpha=0.3, blur=14)
    # winch drum seen end on: flange with spokes, rope coil, iron hub and crank
    ic.shade(ic.mask("ellipse", (WX - WR + 10, WY - WR + 14, WX + WR + 14, WY + WR + 18)), alpha=0.4, blur=8)
    ic.ellipse((WX - WR, WY - WR, WX + WR, WY + WR), "#b08050", "#4e3420", edge=5)
    ic.ellipse((WX - 44, WY - 44, WX + 44, WY + 44), "#b09268", "#6a5234", edge=0)  # rope turns
    for k in range(3):
        rr = 42 - k * 8
        ic.overlay(lambda d, rr=rr: d.ellipse((WX - rr, WY - rr, WX + rr, WY + rr), outline=(70, 52, 30, 170), width=3))
    for k in range(6):
        a = math.pi * k / 3 + 0.4
        ic.line([(WX + math.cos(a) * 14, WY + math.sin(a) * 14), (WX + math.cos(a) * (WR - 6), WY + math.sin(a) * (WR - 6))],
                7, (70, 46, 26))
    ic.overlay(lambda d: d.arc((WX - WR + 6, WY - WR + 6, WX + WR - 6, WY + WR - 6), 170, 280, fill=(255, 226, 180, 120),
                               width=5))
    ic.ellipse((WX - 13, WY - 13, WX + 13, WY + 13), "#6a6668", "#2e2c2e", edge=3)
    ic.line([(WX, WY), (WX + 58, WY - 50)], 12, IRON)  # crank arm
    timber(ic, (WX + 58, WY - 50), (WX + 94, WY - 50), 16, "#a07a50", "#5a3e24")  # crank grip

    # ---- stack of dressed blocks in front
    for x0, x1, y0, y1 in ((330, 470, 800, 890), (476, 620, 802, 892), (626, 760, 800, 892)):
        dressed(ic, x0, x1, y0, y1)
    for x0, x1, y0, y1 in ((384, 540, 716, 800), (548, 690, 716, 802)):
        dressed(ic, x0, x1, y0, y1, lit=1.04)
    ic.shade(ic.mask("rectangle", (330, 890, 800, 920)), alpha=0.5, blur=10)
