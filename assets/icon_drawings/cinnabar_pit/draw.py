"""Cinnabar Pit (cinnabar_pit): an open pit cut down into vermilion-veined rock.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/cinnabar_pit/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/cinnabar_pit

Identity: a crag of pale bedded rock with irregular vermilion cinnabar veins running along the
bedding (forking, pinching out); at its foot a wide timber-collared pit, its far wall red-seamed too,
with a low hand windlass (forked posts, rope drum, L crank) over it and a kibble of red ore coming
up. A big heap of scarlet ore with a pick stands on the right, a basket of picked ore on the left.
Tier 0 of the mercury chain (the retort works add the furnace). Unlike iron_mine (a crag across the
whole icon with a timbered adit) the rock is only the left half, the centre is the windlass over
the pit, and the red is scarlet, not rust.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 41
REFS = ("clay_pit", "stone_quarry", "schwaz_mine", "sand_pit")

WOOD, WOOD_DK = "#8a6240", "#4e3522"
ROCK, ROCK_DK = "#9c8a7a", "#4a3c34"
RED, RED_DK = "#d23a2a", "#5a1210"  # cinnabar: vermilion, lit / shadow
TURF, TURF_DK = "#8e9a58", "#4c5a2a"
EARTH, EARTH_DK = "#8a6a4a", "#4a3626"



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


def tufts(ic: Icon, x: float, y: float, w: float, hang: bool = False) -> None:
    R = ic.random
    lay, d = layer()
    for _ in range(int(w / 5)):
        bx = x + R.uniform(-w / 2, w / 2)
        h = R.uniform(14, 34)
        down = hang and R.random() < 0.5
        tip = (bx + R.uniform(-12, 12), y + (h * 0.8 if down else -h))
        col = (R.randint(92, 128), R.randint(108, 136), R.randint(48, 66), 235)
        d.line([(bx, y), ((bx + tip[0]) / 2 + R.uniform(-4, 4), (y + tip[1]) / 2), tip], fill=col, width=5, joint="curve")
    ic.image.alpha_composite(lay)


def strata(ic: Icon, mask: Image.Image, y0: float, y1: float) -> None:
    """Bedding: wavy darker and lighter bands and a few short joints."""
    R = ic.random
    lay, d = layer()
    y = y0 + 14
    while y < y1:
        pts = [(x, y + 10 * math.sin(x / 90 + y) + (x - 500) * 0.12) for x in range(100, 920, 30)]
        d.line(pts, fill=(40, 30, 26, 110), width=5, joint="curve")
        d.line([(px, py + 6) for px, py in pts], fill=(255, 240, 220, 40), width=3, joint="curve")
        y += R.uniform(34, 54)
    for _ in range(26):
        x, yy = R.uniform(120, 900), R.uniform(y0, y1)
        d.line([(x, yy), (x + R.uniform(-8, 8), yy + R.uniform(20, 40))], fill=(40, 30, 26, 120), width=4)
    composite(ic, lay, mask)


def seam(ic: Icon, path, widths, specks: int = 10) -> None:
    """Cinnabar vein along the bedding: width varies along the path and pinches out at the ends;
    dark crimson edge, vermilion core with bright specks, shadow on the rock under its lower edge."""
    R = ic.random
    P = np.array(path, float)
    W = np.array(widths, float)
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(int(s[-1] / 8), 4)
    ss = np.linspace(0, s[-1], n)
    xs, ys = np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])
    ws = np.interp(ss, s, W) * np.array([R.uniform(0.85, 1.15) for _ in range(n)])
    ws = np.convolve(np.pad(ws, 2, mode="edge"), np.ones(5) / 5, mode="valid")
    dx, dy = np.gradient(xs), np.gradient(ys)
    L = np.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    top = [(x + a * w / 2, y + b * w / 2) for x, y, a, b, w in zip(xs, ys, nx, ny, ws)]
    bot = [(x - a * w / 2, y - b * w / 2) for x, y, a, b, w in zip(xs, ys, nx, ny, ws)]
    m = ic.poly_mask(top + bot[::-1])
    span = (float(ys.min() - W.max()), float(ys.max() + W.max()))
    ic.shade(ImageChops.subtract(ImageChops.offset(m, 3, 9), m), (34, 10, 8), 0.6, blur=2)
    ic.fill(m, "#7e1a14", "#3a0a08", span, noise=0.3)
    core = m.filter(ImageFilter.MinFilter(9))
    ic.fill(core, "#e44a30", "#a42418", span, noise=0.35, chroma=0.08)
    ic.shade(ImageChops.subtract(core, ImageChops.offset(core, 0, -5)), (70, 12, 8), 0.35)  # core rounds off below
    box = core.getbbox()
    if box:
        lay, d = layer()
        for _ in range(specks):
            x, y = R.uniform(box[0], box[2]), R.uniform(box[1], box[3])
            r = R.uniform(2.5, 5)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 196, 168, 235))
        composite(ic, lay, core)


# ---- parts -------------------------------------------------------------------------------------
PCX, PCY, PRX, PRY = 540, 780, 240, 92  # pit mouth
DRUM = 560                               # windlass drum height: low, about half the old frame


def apron(ic: Icon) -> None:
    """Trodden ground in front: red-stained spoil and grit."""
    pts = [(40, 876), (70, 786), (300, 770), (700, 774), (940, 784), (984, 876)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#8e5a44", "#4e2e24", (770, 876), noise=0.3)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (260, 740, 820, 900))), (180, 50, 36), 0.3, blur=20)
    for _ in range(40):
        x, y = ic.random.uniform(60, 960), ic.random.uniform(800, 864)
        r = ic.random.uniform(5, 10)
        c = "#c04a38" if ic.random.random() < 0.5 else "#a89480"
        ic.fill(ic.poly_mask(ic.jitter(x, y, r, r * 0.7, 6, 0.3)), c, "#3e2820", (y - r, y + r), noise=0.2)
    ic.outline(pts)


def bed(x: float, y0: float, amp: float = 12, ph: float = 0.0) -> float:
    """A bedding line through (500, y0): the strata dip gently to the right and wave a little."""
    return y0 + (x - 500) * 0.12 + amp * math.sin(x / 90 + ph)


def outcrop(ic: Icon) -> None:
    """Crag of pale grey bedded rock with irregular cinnabar veins along the bedding, turf crown."""
    crag = [(70, 800), (76, 660), (96, 600), (104, 520), (136, 470), (150, 400), (184, 350), (200, 300), (260, 262),
            (300, 284), (330, 270), (390, 236), (450, 270), (486, 300), (520, 350), (536, 410), (566, 450), (600, 500),
            (660, 520), (730, 548), (800, 590), (840, 640), (850, 800)]
    m = ic.poly_mask(crag)
    ic.fill(m, "#b2a494", "#5a4c42", radial=(160, 260, 700), noise=0.28, chroma=0.12)
    strata(ic, m, 250, 800)
    with ic.clipped(m):
        ic.shade(ic.mask("ellipse", (100, 380, 560, 760)), (170, 50, 36), 0.12, blur=50)
        for f in range(4):  # facets: lit planes upper left, shadow planes lower right
            pts = ic.jitter(ic.random.uniform(120, 520), ic.random.uniform(380, 720), 90, 60, 5, 0.3)
            ic.shade(ic.poly_mask(pts), (0, 0, 0) if f % 2 else (255, 244, 226), 0.16 if f % 2 else 0.1, blur=4)
        # main vein: thick in the middle, forking to the right, pinching out at both ends
        xs = np.linspace(96, 590, 12)
        main = [(x, bed(x, 500, 14, 0.4)) for x in xs]
        seam(ic, main, [2, 14, 26, 36, 30, 22, 30, 24, 16, 10, 5, 1], 16)
        fx = np.linspace(330, 520, 6)
        seam(ic, [(x, bed(x, 500, 14, 0.4) + (x - 330) * 0.42) for x in fx], [16, 14, 12, 9, 5, 1], 5)
        # thinner vein higher up, lens-shaped
        xs = np.linspace(220, 540, 8)
        seam(ic, [(x, bed(x, 372, 10, 1.7)) for x in xs], [1, 10, 18, 22, 14, 18, 8, 1], 8)
        # lower vein: broken in two stretches
        xs = np.linspace(90, 330, 7)
        seam(ic, [(x, bed(x, 650, 12, 2.6)) for x in xs], [1, 14, 24, 20, 26, 12, 1], 10)
        xs = np.linspace(380, 600, 6)
        seam(ic, [(x, bed(x, 668, 10, 2.6)) for x in xs], [1, 8, 14, 18, 10, 2], 5)
        ic.shade(ic.mask("rectangle", (0, 700, SIZE, SIZE)), alpha=0.3, blur=30)
        ic.shade(ic.poly_mask([(560, 460), (900, 460), (900, 820), (560, 820)]), alpha=0.3, blur=30)
    ic.outline(crag)
    turf = [(150, 400), (184, 350), (200, 300), (260, 262), (300, 284), (330, 270), (390, 236), (450, 270), (486, 300),
            (510, 336), (450, 316), (390, 280), (330, 306), (260, 300), (210, 340), (170, 404)]
    ic.poly(turf, TURF, TURF_DK, noise=0.3, edge=4)
    for x, y, w in ((210, 300, 50), (300, 290, 50), (420, 262, 50)):
        tufts(ic, x, y, w)


def log(ic: Icon, p0, p1, r: float) -> None:
    """Round log: lit top, dark underside, bark streaks, cut end with rings at p1."""
    timber(ic, p0, p1, r * 2, "#9a7048", "#4a3220")
    x, y = p1
    ic.ellipse((x - r * 0.7, y - r, x + r * 0.7, y + r), "#d2a86e", "#8a6038", edge=4)
    ic.overlay(lambda d: d.ellipse((x - r * 0.35, y - r * 0.5, x + r * 0.35, y + r * 0.5), outline=(120, 80, 44, 200),
                                   width=3))


def pit(ic: Icon) -> None:
    """Wide pit mouth: red-seamed far wall, dark opening, timber collar of logs, lit near rim."""
    box = (PCX - PRX, PCY - PRY, PCX + PRX, PCY + PRY)
    mouth = ic.mask("ellipse", box)
    lip = ic.mask("ellipse", (box[0] - 30, box[1] - 16, box[2] + 30, box[3] + 20))
    ic.fill(lip, "#9a664c", "#4e2e24", (box[1] - 16, box[3] + 20), noise=0.3)
    ic.fill(mouth, ROCK, ROCK_DK, (box[1], box[3]), noise=0.28, chroma=0.12)
    with ic.clipped(mouth):
        strata(ic, mouth, box[1], box[3])
        xs = np.linspace(box[0], box[2] - 60, 8)
        seam(ic, [(x, box[1] + 40 + (x - PCX) * 0.08 + 6 * math.sin(x / 50)) for x in xs],
             [1, 14, 26, 18, 28, 20, 10, 1], 8)
        xs = np.linspace(PCX - 40, box[2], 5)
        seam(ic, [(x, box[1] + 62 + (x - PCX) * 0.08) for x in xs], [1, 10, 16, 10, 1], 4)
        dark = ic.mask("ellipse", (box[0] + 22, box[1] + 84, box[2] - 22, box[3] + 70))
        ic.fill(dark, "#2e201a", "#0c0806", (box[1] + 84, box[3]), noise=0.08)
        ic.shade(ImageChops.subtract(dark.filter(ImageFilter.MaxFilter(21)), dark), alpha=0.5, blur=6)
        ic.shade(ic.mask("rectangle", (0, box[1], SIZE, box[1] + 20)), alpha=0.45, blur=8)
    # lit near rim of trodden ground
    near = ImageChops.subtract(lip, ic.mask("ellipse", (box[0] - 6, box[1] - 10, box[2] + 6, box[3] - 4)))
    near = ic.intersect(near, ic.mask("rectangle", (0, PCY, SIZE, SIZE)))
    ic.shade(near, (255, 214, 176), 0.35)
    ic.overlay(lambda d: d.ellipse(box, outline=(40, 26, 16, 200), width=5))
    # timber collar: a log along the far rim and one down each side
    log(ic, (PCX + 40, box[1] + 2), (PCX - PRX - 26, box[1] + 14), 20)
    log(ic, (box[0] + 30, box[1] + 8), (box[0] - 10, PCY + 30), 18)
    log(ic, (box[2] - 30, box[1] + 4), (box[2] + 12, PCY + 26), 18)


def windlass(ic: Icon) -> None:
    """Low hand windlass over the pit: two forked posts, thick rope drum, L crank, kibble of ore."""
    X0, X1 = PCX - PRX + 6, PCX + PRX - 6
    for x, sgn in ((X0, -1), (X1, 1)):
        foot = PCY + 6
        # short A-frame: two splayed legs meeting under the drum axle, a cross tie
        timber(ic, (x - 62, foot), (x - 4, DRUM - 8), 24, "#9a7048", "#523823")
        timber(ic, (x + 62, foot), (x + 4, DRUM - 8), 24, "#9a7048", "#523823")
        timber(ic, (x - 40, DRUM + 130), (x + 40, DRUM + 130), 14, "#9a7048", "#523823")
    cx = PCX
    # rope down to the kibble over the mouth
    ky0, ky1 = PCY - 118, PCY - 40
    ic.line([(cx, DRUM + 24), (cx + 2, ky0 - 40)], 9, (60, 46, 30))
    ic.line([(cx, DRUM + 24), (cx + 2, ky0 - 40)], 4, (190, 160, 110))
    kx0, kx1 = cx - 52, cx + 52
    ic.overlay(lambda d: d.arc((kx0 + 4, ky0 - 46, kx1 - 4, ky0 + 24), 185, 355, fill=(40, 38, 38, 255), width=7))
    for x in (cx - 28, cx, cx + 28):
        ic.chunk(x, ky0 - 4, 17, RED, RED_DK, (255, 200, 180))
    ic.poly([(kx0, ky0), (kx1, ky0), (kx1 - 10, ky1), (kx0 + 10, ky1)], "#a47448", "#4e3420", (kx0, kx1), vertical=False)
    ic.line([(kx0 + 3, ky0 + 18), (kx1 - 3, ky0 + 18)], 8, (48, 46, 48))
    ic.line([(kx0 + 8, ky1 - 16), (kx1 - 8, ky1 - 16)], 8, (48, 46, 48))
    # thick drum with turns of rope in the middle
    dm = ic.mask("rectangle", (X0 - 14, DRUM - 32, X1 + 14, DRUM + 32))
    ic.fill(dm, "#b08456", "#5a3e26", (DRUM - 32, DRUM + 32), noise=0.2)
    rope = ic.mask("rectangle", (cx - 90, DRUM - 36, cx + 90, DRUM + 36))
    ic.fill(rope, "#c8aa76", "#6e5634", (DRUM - 36, DRUM + 36), noise=0.25)
    ic.overlay(lambda d: [d.line([(x, DRUM - 36), (x + 14, DRUM + 36)], fill=(70, 52, 30, 220), width=6)
                          for x in range(int(cx - 96), int(cx + 90), 16)], rope)
    ic.shade(ic.intersect(ImageChops.lighter(dm, rope), ic.mask("rectangle", (0, DRUM + 8, SIZE, SIZE))), alpha=0.35)
    ic.line([(X0 - 12, DRUM - 22), (X1 + 12, DRUM - 22)], 5, (255, 232, 190, 110))
    ic.outline([(X0 - 14, DRUM - 32), (X1 + 14, DRUM - 32), (X1 + 14, DRUM + 32), (X0 - 14, DRUM + 32)], 4)
    ic.outline([(cx - 90, DRUM - 36), (cx + 90, DRUM - 36), (cx + 90, DRUM + 36), (cx - 90, DRUM + 36)], 4)
    for x in (X0, X1):
        ic.ellipse((x - 16, DRUM - 16, x + 16, DRUM + 16), "#6a6664", "#2e2c2c", edge=4)
    # L-shaped iron crank sticking out at the left end, over the rock, wooden handle
    ex = X0 - 14
    ic.line([(ex, DRUM), (ex - 70, DRUM)], 20, (30, 28, 28))
    ic.line([(ex, DRUM - 3), (ex - 66, DRUM - 3)], 8, (130, 128, 124))
    ic.line([(ex - 70, DRUM - 8), (ex - 70, DRUM + 88)], 20, (30, 28, 28))
    ic.line([(ex - 67, DRUM - 4), (ex - 67, DRUM + 84)], 8, (130, 128, 124))
    timber(ic, (ex - 66, DRUM + 88), (ex - 136, DRUM + 88), 26, "#c09a6a", "#6a4a2c")


def pick(ic: Icon) -> None:
    """Pick stuck in the heap: light ash handle, dark iron head."""
    ic.line([(900, 850), (950, 610)], 22, (40, 26, 16))
    ic.line([(900, 850), (950, 610)], 13, (206, 170, 120))
    ic.line([(897, 846), (946, 614)], 4, (240, 214, 170))
    ic.draw.arc((876, 572, 1016, 652), 190, 330, fill=(28, 18, 12, 255), width=22)
    ic.draw.arc((876, 572, 1016, 652), 192, 328, fill=(84, 82, 80, 255), width=13)
    ic.overlay(lambda d: d.arc((880, 576, 1012, 648), 200, 300, fill=(210, 210, 204, 160), width=4))


def draw(ic: Icon) -> None:
    apron(ic)
    outcrop(ic)
    pit(ic)
    windlass(ic)
    ic.heap(740, 1010, 862, 540, 54, 6, body=("#8a2a20", "#3a100c"), lump=(RED, RED_DK),
            odd=("#a89888", "#4a3e36"), odd_share=0.16)
    pick(ic)
    # basket of picked ore, front left
    ic.basket(56, 724, 232, 864)
    for i in range(6):
        ic.chunk(80 + i * 28 + ic.random.uniform(-4, 4), 716 + ic.random.uniform(-8, 4), 19, "#e04a36", RED_DK,
                 (255, 210, 190))
